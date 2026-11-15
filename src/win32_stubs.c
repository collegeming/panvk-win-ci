/* Minimal Windows shims for symbols reached by Mesa's generic pan_kmod
 * and non-virtio paths.  The kbase/vdrm path never calls the DRM fallbacks.
 * SPDX-License-Identifier: MIT
 */
#include <errno.h>
#include <stddef.h>
#include <stdint.h>

#include "xf86drm.h"
#include "sys/mman.h"

#ifndef MAP_FAILED
#define MAP_FAILED ((void *)(uintptr_t)~0ull)
#endif

void *mmap(void *addr, size_t len, int prot, int flags, int fd, off_t off)
{
   (void)addr; (void)len; (void)prot; (void)flags; (void)fd; (void)off;
   errno = ENOSYS;
   return MAP_FAILED;
}

int munmap(void *addr, size_t len)
{
   (void)addr; (void)len;
   errno = ENOSYS;
   return -1;
}

drmVersionPtr drmGetVersion(int fd)
{
   (void)fd;
   errno = ENOSYS;
   return NULL;
}

void drmFreeVersion(drmVersionPtr v)
{
   (void)v;
}

int drmPrimeFDToHandle(int fd, int prime_fd, uint32_t *handle)
{
   (void)fd; (void)prime_fd; (void)handle;
   errno = ENOSYS;
   return -1;
}

int drmCloseBufferHandle(int fd, uint32_t handle)
{
   (void)fd; (void)handle;
   errno = ENOSYS;
   return -1;
}

int drmIoctl(int fd, unsigned long request, void *arg)
{
   (void)fd; (void)request; (void)arg;
   errno = ENOSYS;
   return -1;
}

int drmPrimeHandleToFD(int fd, uint32_t handle, uint32_t flags, int *prime_fd)
{
   (void)fd; (void)handle; (void)flags; (void)prime_fd;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjCreate(int fd, uint32_t flags, uint32_t *handle)
{
   (void)fd; (void)flags; (void)handle;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjDestroy(int fd, uint32_t handle)
{
   (void)fd; (void)handle;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjHandleToFD(int fd, uint32_t handle, int *obj_fd)
{
   (void)fd; (void)handle; (void)obj_fd;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjFDToHandle(int fd, int obj_fd, uint32_t *handle)
{
   (void)fd; (void)obj_fd; (void)handle;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjImportSyncFile(int fd, uint32_t handle, int sync_file_fd)
{
   (void)fd; (void)handle; (void)sync_file_fd;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjExportSyncFile(int fd, uint32_t handle, int *sync_file_fd)
{
   (void)fd; (void)handle; (void)sync_file_fd;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjWait(int fd, uint32_t *handles, unsigned num_handles,
                   int64_t timeout_nsec, unsigned flags,
                   uint32_t *first_signaled)
{
   (void)fd; (void)handles; (void)num_handles; (void)timeout_nsec;
   (void)flags; (void)first_signaled;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjReset(int fd, const uint32_t *handles, uint32_t handle_count)
{
   (void)fd; (void)handles; (void)handle_count;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjSignal(int fd, const uint32_t *handles, uint32_t handle_count)
{
   (void)fd; (void)handles; (void)handle_count;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjTimelineWait(int fd, uint32_t *handles, uint64_t *points,
                           unsigned num_handles, int64_t timeout_nsec,
                           unsigned flags, uint32_t *first_signaled)
{
   (void)fd; (void)handles; (void)points; (void)num_handles;
   (void)timeout_nsec; (void)flags; (void)first_signaled;
   errno = ENOSYS;
   return -1;
}

int drmSyncobjTransfer(int fd, uint32_t dst_handle, uint64_t dst_point,
                       uint32_t src_handle, uint64_t src_point, uint32_t flags)
{
   (void)fd; (void)dst_handle; (void)dst_point; (void)src_handle;
   (void)src_point; (void)flags;
   errno = ENOSYS;
   return -1;
}

/* Mesa's DRM-syncobj vk_sync type is not built on Windows (no libdrm); the
 * kbase path uses kbase_cpu_sync.  Async-bind helpers still reference these
 * two runtime symbols, so satisfy the link. */
struct vk_device;
struct vk_sync;
struct vk_sync_wait;
struct vk_sync_signal;

void vk_drm_syncobj_finish(struct vk_device *device, struct vk_sync *sync)
{
   (void)device; (void)sync;
}

int vk_drm_syncobj_copy_payloads(struct vk_device *device, uint32_t wait_count,
                                 const struct vk_sync_wait *waits,
                                 uint32_t signal_count,
                                 const struct vk_sync_signal *signals)
{
   (void)device; (void)wait_count; (void)waits;
   (void)signal_count; (void)signals;
   return -1;
}

/* Android libunwind backtrace used by pan_trace: no frames on Windows. */
struct _Unwind_Context;
typedef int _Unwind_Reason_Code;
typedef _Unwind_Reason_Code (*_Unwind_Trace_Fn)(struct _Unwind_Context *, void *);

_Unwind_Reason_Code _Unwind_Backtrace(_Unwind_Trace_Fn fn, void *arg)
{
   (void)fn; (void)arg;
   return 5; /* _URC_END_OF_STACK */
}

uintptr_t _Unwind_GetIP(struct _Unwind_Context *ctx)
{
   (void)ctx;
   return 0;
}
