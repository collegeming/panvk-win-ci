/*
 * kbv over vdrm/WDDM: Windows implementation of the PanVK kbase virtio
 * transport.  This file is the Windows counterpart of mali_kbase_virtio.c:
 * the kbv request layout and the host-side ABI are unchanged, but every
 * /dev/dri + ioctl + mmap operation is replaced by the vdrm device that the
 * virtio_wddm_rs.sys KMD exposes (D3DKMT escapes).
 *
 * The device/context/control page are created by vdrm_wddm_connect(); the
 * control page is vdev->shmem and its responses live at vdev->rsp_mem.
 *
 * SPDX-License-Identifier: MIT
 */
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>

#include "util/simple_mtx.h"
#include "vdrm.h"
#include "drm-uapi/panthor_drm.h"
#include "mali_kbase_virtio.h"
#include "kbase_kmod.h"

#define KBV_CONTEXT_TYPE 0x4b424153u /* "KBAS" */
#define KBV_BLOB_MAPPABLE 1u
#define KBV_MAP_FAILED ((void *)(uintptr_t)~0ull)

struct kbv_req {
   uint32_t cmd, len, seqno, rsp_off;
   uint32_t handle, offset, size, reserved;
   uint8_t data[1024];
};
struct kbv_rsp {
   uint32_t len;
   int32_t status;
   uint32_t handle, size;
   uint64_t value;
   uint8_t data[1024];
};
struct kbv_ctx {
   int fd;
   int error;
   uint32_t gem, seqno, rsp_off;
   struct vdrm_device *vdev;
   struct { uint32_t handle; uint32_t gem; void *ptr; uint64_t size; } bo[1024];
   struct { uint32_t gem; uint64_t va; void *ptr; } queue[32];
};
static struct kbv_ctx contexts[16];
static simple_mtx_t lock = SIMPLE_MTX_INITIALIZER;

static struct kbv_ctx *lookup(int fd)
{
   for (unsigned i = 0; i < 16; i++)
      if (contexts[i].vdev && contexts[i].fd == fd) return &contexts[i];
   return NULL;
}

bool kbv_has(int fd)
{
   simple_mtx_lock(&lock);
   bool found = lookup(fd) != NULL;
   simple_mtx_unlock(&lock);
   return found;
}

bool kbv_has_error(int fd)
{
   simple_mtx_lock(&lock);
   struct kbv_ctx *ctx = lookup(fd);
   int error = ctx ? ctx->error : 0;
   simple_mtx_unlock(&lock);
   if (error) errno = error;
   return error != 0;
}

static int latch_error(int fd, int ret)
{
   if (ret >= 0) return ret;
   int saved = errno ? errno : EIO;
   simple_mtx_lock(&lock);
   struct kbv_ctx *ctx = lookup(fd);
   if (ctx && !ctx->error) {
      ctx->error = saved;
      fprintf(stderr, "kbase vdrm: context fd=%d failed: %s\n", fd, strerror(saved));
   }
   simple_mtx_unlock(&lock);
   errno = saved;
   return ret;
}

int kbv_init(int fd, uint16_t *major, uint16_t *minor)
{
   struct vdrm_device *vdev = vdrm_device_connect(-1, KBV_CONTEXT_TYPE);
   if (!vdev) {
      errno = ENODEV;
      return -1;
   }
   if (!vdev->shmem || !vdev->rsp_mem ||
       vdev->caps.wire_format_version != 2 ||
       vdev->caps.context_type != KBV_CONTEXT_TYPE) {
      vdrm_device_close(vdev);
      errno = EPROTO;
      return -1;
   }

   simple_mtx_lock(&lock);
   struct kbv_ctx *ctx = NULL;
   for (unsigned i = 0; i < 16; i++)
      if (!contexts[i].vdev) { ctx = &contexts[i]; break; }
   if (!ctx) {
      simple_mtx_unlock(&lock);
      vdrm_device_close(vdev);
      errno = EMFILE;
      return -1;
   }
   *ctx = (struct kbv_ctx){
      .fd = fd,
      .vdev = vdev,
   };
   simple_mtx_unlock(&lock);
   *major = vdev->caps.version_major;
   *minor = vdev->caps.version_minor;
   return 1;
}

void kbv_finish(int fd)
{
   simple_mtx_lock(&lock);
   struct kbv_ctx *ctx = lookup(fd);
   struct vdrm_device *vdev = ctx ? ctx->vdev : NULL;
   if (ctx) memset(ctx, 0, sizeof(*ctx));
   simple_mtx_unlock(&lock);
   if (vdev) vdrm_device_close(vdev);
}

static int rpc(int fd, struct kbv_req *q, struct kbv_rsp *r)
{
   int ret = -1;
   simple_mtx_lock(&lock);
   struct kbv_ctx *ctx = lookup(fd);
   if (!ctx) { errno = ENODEV; goto out; }
   if (!ctx->vdev->shmem || ctx->vdev->shmem->rsp_mem_offset != 8) {
      errno = EPROTO;
      goto out;
   }
   q->len = sizeof(*q);
   if (ctx->rsp_off + sizeof(*r) > ctx->vdev->rsp_mem_len)
      ctx->rsp_off = 0;
   q->rsp_off = ctx->rsp_off;
   ctx->rsp_off = (ctx->rsp_off + sizeof(*r) + 7) & ~7u;

   struct kbv_rsp *shared_rsp =
      (void *)((uint8_t *)ctx->vdev->rsp_mem + q->rsp_off);
   shared_rsp->len = sizeof(*r);

   struct vdrm_execbuf_params p = {
      .req = (struct vdrm_ccmd_req *)q,
   };
   if (vdrm_execbuf(ctx->vdev, &p))
      goto out;
   vdrm_host_sync(ctx->vdev, (struct vdrm_ccmd_req *)q);
   if (__atomic_load_n(&ctx->vdev->shmem->seqno, __ATOMIC_ACQUIRE) != q->seqno) {
      errno = EPROTO;
      goto out;
   }
   memcpy(r, (uint8_t *)ctx->vdev->rsp_mem + q->rsp_off, sizeof(*r));
   if (r->len != sizeof(*r)) { errno = EPROTO; goto out; }
   if (r->status) { errno = -r->status; goto out; }
   ret = 0;
out:
   simple_mtx_unlock(&lock);
   return ret;
}

uint8_t *kbv_props(int fd, size_t *size)
{
   struct kbv_req q = { .cmd = 9 };
   struct kbv_rsp r;
   if (rpc(fd, &q, &r)) return NULL;
   if (!r.value || r.value > 65536) { errno = EPROTO; return NULL; }
   *size = r.value;
   uint8_t *buf = malloc(*size);
   if (!buf) return NULL;
   for (size_t off = 0; off < *size;) {
      q.offset = off;
      q.size = 1024;
      if (rpc(fd, &q, &r) || !r.size || r.size > 1024 || r.size > *size - off) {
         free(buf);
         return NULL;
      }
      memcpy(buf + off, r.data, r.size);
      off += r.size;
   }
   return buf;
}

int kbv_csif(int fd, struct drm_panthor_csif_info *info)
{
   struct kbv_req q = { .cmd = 10 };
   struct kbv_rsp r;
   if (rpc(fd, &q, &r)) return -1;
   if (r.size != sizeof(*info)) { errno = EPROTO; return -1; }
   memcpy(info, r.data, sizeof(*info));
   return 0;
}

int kbv_bo_alloc(int fd, uint64_t size, uint64_t flags, bool shared, uint32_t *handle,
                 uint32_t *gem, uint64_t *gpu_va, void **map)
{
   if (size > UINT32_MAX || flags > UINT32_MAX) { errno = EOVERFLOW; return -1; }
   struct kbv_req q = { .cmd = 11, .size = size, .handle = flags, .reserved = shared };
   struct kbv_rsp r;
   if (rpc(fd, &q, &r)) return -1;
   *handle = r.handle;
   *gpu_va = r.value;

   struct vdrm_ccmd_req dummy = { 0 };
   /* vdrm_bo_create() belongs to a device; get it from the context. */
   simple_mtx_lock(&lock);
   struct kbv_ctx *ctx = lookup(fd);
   struct vdrm_device *vdev = ctx ? ctx->vdev : NULL;
   simple_mtx_unlock(&lock);
   if (!vdev) { errno = ENODEV; return -1; }

   uint32_t vgem = vdrm_bo_create(vdev, size, KBV_BLOB_MAPPABLE, r.handle, 0, &dummy);
   if (!vgem) goto fail;
   void *ptr = vdrm_bo_map(vdev, vgem, size, NULL);
   if (ptr == KBV_MAP_FAILED) {
      vdrm_bo_close(vdev, vgem);
      goto fail;
   }

   simple_mtx_lock(&lock);
   ctx = lookup(fd);
   unsigned slot;
   for (slot = 0; ctx && slot < 1024 && ctx->bo[slot].ptr; slot++);
   if (ctx && slot < 1024) {
      ctx->bo[slot] = (typeof(ctx->bo[slot])){ .handle = *handle, .gem = vgem,
                                               .ptr = ptr, .size = size };
   }
   simple_mtx_unlock(&lock);
   if (!ctx || slot >= 1024) {
      vdrm_bo_close(vdev, vgem);
      errno = ENOSPC;
      goto fail;
   }
   *gem = vgem;
   *map = ptr;
   return 0;

fail:
   q = (struct kbv_req){ .cmd = 4, .handle = *handle };
   rpc(fd, &q, &r);
   return -1;
}

void kbv_bo_free(int fd, uint32_t handle, uint32_t gem, void *map, uint64_t size)
{
   (void)size;
   simple_mtx_lock(&lock);
   struct kbv_ctx *ctx = lookup(fd);
   struct vdrm_device *vdev = ctx ? ctx->vdev : NULL;
   if (ctx) for (unsigned i = 0; i < 1024; i++)
      if (ctx->bo[i].ptr == map) memset(&ctx->bo[i], 0, sizeof(ctx->bo[i]));
   simple_mtx_unlock(&lock);
   if (vdev) {
      if (gem) vdrm_bo_close(vdev, gem);
   }
   struct kbv_req q = { .cmd = 4, .handle = handle };
   struct kbv_rsp r;
   rpc(fd, &q, &r);
}

int kbv_bo_sync(int fd, uint32_t handle, uint64_t offset, uint64_t size, uint8_t type)
{
   if (offset > UINT32_MAX || size > UINT32_MAX) { errno = EOVERFLOW; return -1; }
   struct kbv_req q = { .cmd = 12, .handle = handle, .offset = offset, .size = size };
   struct kbv_rsp r;
   q.data[0] = type;
   return latch_error(fd, rpc(fd, &q, &r));
}

int kbv_ioctl(int fd, unsigned long command, ...)
{
   va_list args;
   void *arg = NULL;
   va_start(args, command);
   if (_IOC_SIZE(command)) arg = va_arg(args, void *);
   va_end(args);
   if (!kbv_has(fd)) { errno = ENODEV; return -1; }
   if (_IOC_SIZE(command) > 1024) { errno = EINVAL; return -1; }
   struct kbv_req q = { .cmd = 13, .handle = command, .size = _IOC_SIZE(command) };
   struct kbv_rsp r;
   if (q.size) memcpy(q.data, arg, q.size);
   if (rpc(fd, &q, &r)) return -1;
   if (r.size != q.size) { errno = EPROTO; return -1; }
   if (q.size) memcpy(arg, r.data, q.size);
   return 0;
}

int kbv_cpu_sync(const void *ptr, size_t size, uint8_t type)
{
   uintptr_t addr = (uintptr_t)ptr;
   int fd = -1;
   uint32_t handle = 0;
   uint64_t offset = 0;
   simple_mtx_lock(&lock);
   for (unsigned c = 0; c < 16 && fd < 0; c++) {
      if (!contexts[c].vdev) continue;
      for (unsigned b = 0; b < 1024; b++) {
         uintptr_t start = (uintptr_t)contexts[c].bo[b].ptr;
         uint64_t len = contexts[c].bo[b].size;
         if (start && addr >= start && addr - start < len && size <= len - (addr - start)) {
            fd = contexts[c].fd;
            handle = contexts[c].bo[b].handle;
            offset = addr - start;
            break;
         }
      }
   }
   simple_mtx_unlock(&lock);
   if (fd < 0) return 0;
   return kbv_bo_sync(fd, handle, offset, size, type) ? -1 : 1;
}

static int queue_rpc(int fd, uint32_t op, uint64_t va, uint32_t csi,
                     uint32_t size, uint32_t group, struct kbv_rsp *r)
{
   struct kbv_req q = { .cmd = 14, .handle = op, .offset = csi, .size = size };
   memcpy(q.data, &va, 8);
   memcpy(q.data + 8, &group, 4);
   return rpc(fd, &q, r);
}

bool kbv_queue_bind(int fd, uint32_t group, uint32_t csi, uint64_t va,
                    uint32_t size, struct kbase_kmod_csf_user_io *io)
{
   struct kbv_rsp r;
   if (queue_rpc(fd, 0, va, csi, size, group, &r)) return false;
   simple_mtx_lock(&lock);
   struct kbv_ctx *ctx = lookup(fd);
   struct vdrm_device *vdev = ctx ? ctx->vdev : NULL;
   simple_mtx_unlock(&lock);
   if (!vdev) return false;

   struct vdrm_ccmd_req dummy = { 0 };
   uint32_t gem = vdrm_bo_create(vdev, 12288, KBV_BLOB_MAPPABLE, r.handle, 0, &dummy);
   if (!gem) goto fail;
   void *ptr = vdrm_bo_map(vdev, gem, 12288, NULL);
   if (ptr == KBV_MAP_FAILED) { vdrm_bo_close(vdev, gem); goto fail; }

   simple_mtx_lock(&lock);
   ctx = lookup(fd);
   unsigned slot;
   for (slot = 0; ctx && slot < 32 && ctx->queue[slot].ptr; slot++);
   if (ctx && slot < 32) {
      ctx->queue[slot] = (typeof(ctx->queue[slot])){ .ptr = ptr, .va = va, .gem = gem };
   }
   simple_mtx_unlock(&lock);
   if (!ctx || slot >= 32) {
      vdrm_bo_close(vdev, gem);
      goto fail;
   }
   *io = (struct kbase_kmod_csf_user_io){
      .map = ptr,
      .doorbell = ptr,
      .input = (uint8_t *)ptr + 4096 + 16 * csi,
      .output = (uint8_t *)ptr + 8192 + 16 * csi,
   };
   return true;

fail:
   queue_rpc(fd, 1, va, 0, 0, 0, &r);
   return false;
}

void kbv_queue_term(int fd, uint64_t va, struct kbase_kmod_csf_user_io *io)
{
   simple_mtx_lock(&lock);
   struct kbv_ctx *ctx = lookup(fd);
   struct vdrm_device *vdev = ctx ? ctx->vdev : NULL;
   if (ctx) for (unsigned i = 0; i < 32; i++) {
      if (!ctx->queue[i].ptr || ctx->queue[i].va != va) continue;
      if (vdev) vdrm_bo_close(vdev, ctx->queue[i].gem);
      memset(&ctx->queue[i], 0, sizeof(ctx->queue[i]));
   }
   simple_mtx_unlock(&lock);
   struct kbv_rsp r;
   queue_rpc(fd, 1, va, 0, 0, 0, &r);
   memset(io, 0, sizeof(*io));
}

int kbv_queue_kick(int fd, uint64_t va)
{
   if (kbv_has_error(fd)) return -1;
   struct kbv_rsp r;
   return latch_error(fd, queue_rpc(fd, 2, va, 0, 0, 0, &r));
}

int kbv_wait_event(int fd, int64_t timeout_ns)
{
   if (kbv_has_error(fd)) return -1;
   uint32_t ms = timeout_ns < 0 || timeout_ns > 20000000 ? 20 : (timeout_ns + 999999) / 1000000;
   struct kbv_rsp r;
   return latch_error(fd, queue_rpc(fd, 3, 0, 0, ms, 0, &r));
}

uint64_t kbv_alias_create(int fd, uint64_t va, uint64_t size, uint32_t nents)
{
   if (size > UINT32_MAX) { errno = EOVERFLOW; return 0; }
   struct kbv_req q = { .cmd = 15, .offset = nents, .size = size };
   struct kbv_rsp r;
   memcpy(q.data, &va, 8);
   return rpc(fd, &q, &r) ? 0 : r.value;
}

void kbv_alias_destroy(int fd, uint64_t va)
{
   struct kbv_req q = { .cmd = 15, .handle = 1 };
   struct kbv_rsp r;
   memcpy(q.data, &va, 8);
   rpc(fd, &q, &r);
}
