#!/usr/bin/env python3
"""Apply the Windows PanVK transport/build edits to a manet Mesa tree.

The edits are intentionally string based: the manet branch is a moving
development fork and a context patch would rot faster than these few
well-delimited changes.  Every missing anchor is reported; the CI build then
shows the real error.
"""
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "mesa")
changes = 0
misses = []


def sub(rel, old, new, count=1, required=True):
    global changes
    p = root / rel
    if not p.exists():
        misses.append(f"{rel}: file missing")
        return False
    s = p.read_text(encoding="utf-8", errors="surrogateescape")
    if old not in s:
        misses.append(f"{rel}: anchor missing: {old[:70]!r}")
        return False
    s = s.replace(old, new, count)
    p.write_text(s, encoding="utf-8", errors="surrogateescape")
    changes += 1
    return True


def wrap(rel, start_marker, end_marker, before):
    global changes
    p = root / rel
    if not p.exists():
        misses.append(f"{rel}: file missing")
        return False
    s = p.read_text(encoding="utf-8", errors="surrogateescape")
    a = s.find(start_marker)
    b = s.find(end_marker, a + 1)
    if a < 0 or b < 0:
        misses.append(f"{rel}: wrap markers missing")
        return False
    s = s[:a] + before + s[a:b] + "#endif\n\n" + s[b:]
    p.write_text(s, encoding="utf-8", errors="surrogateescape")
    changes += 1
    return True


# --------------------------------------------------------------------------
# Windows header shadow tree (POSIX/libdrm stand-ins).
# --------------------------------------------------------------------------
sub("include/meson.build",
    "inc_include = [include_directories('.')]",
    "inc_include = [include_directories('.'), include_directories('win32-compat')]")

# --------------------------------------------------------------------------
# Windows M2: no glslang/BVH ray-tracing build, and only the G2-Ultra (v15)
# per-arch PanVK library.  Both cut unrelated tool and compile surface.
# --------------------------------------------------------------------------
sub("meson.build",
    "with_bvh = with_amd_vk or with_intel_vk or with_swrast_vk or with_freedreno_vk or with_panfrost_vk",
    "with_bvh = (with_amd_vk or with_intel_vk or with_swrast_vk or with_freedreno_vk or with_panfrost_vk) and host_machine.system() != 'windows'")

sub("src/panfrost/vulkan/meson.build",
    "subdir('bvh')\n\nrt_archs = [15]",
    "if host_machine.system() != 'windows'\n"
    "  subdir('bvh')\n"
    "  rt_archs = [15]\n"
    "else\n"
    "  panvk_bvh_spv = []\n"
    "  rt_archs = []\n"
    "endif")

sub("src/panfrost/vulkan/meson.build",
    "foreach arch : [6, 7, 10, 11, 12, 13, 14, 15]",
    "foreach arch : [15]")

sub("src/panfrost/vulkan/meson.build",
    "    '--device-prefix', 'panvk_v6', '--device-prefix', 'panvk_v7',\n"
    "    '--device-prefix', 'panvk_v9', '--device-prefix', 'panvk_v10',\n"
    "    '--device-prefix', 'panvk_v11', '--device-prefix', 'panvk_v12',\n"
    "    '--device-prefix', 'panvk_v13', '--device-prefix', 'panvk_v14',\n"
    "    '--device-prefix', 'panvk_v15',\n",
    "    '--device-prefix', 'panvk_v15',\n")

sub("src/panfrost/vulkan/panvk_macros.h",
    "#else\n#error \"Unsupported arch\"\n#endif\n#endif\n\n#endif\n",
    "#else\n#error \"Unsupported arch\"\n#endif\n#endif\n\n"
    "#ifdef _WIN32\n"
    "/* M2 targets only Mali-G2-Ultra (v15); the other per-arch libraries are\n"
    " * not built on Windows, so resolve every dispatch to v15. */\n"
    "#undef panvk_arch_dispatch\n"
    "#undef panvk_arch_dispatch_ret\n"
    "#define panvk_arch_dispatch(arch, name, ...) \\\n"
    "   do { (void)(arch); panvk_arch_name(name, v15)(__VA_ARGS__); } while (0)\n"
    "#define panvk_arch_dispatch_ret(arch, name, ret, ...) \\\n"
    "   do { (void)(arch); ret = panvk_arch_name(name, v15)(__VA_ARGS__); } while (0)\n"
    "#endif\n\n"
    "#endif\n")

# --------------------------------------------------------------------------
# Windows portability: MSVC/clang-cl ABI and POSIX shims.
# --------------------------------------------------------------------------
sub("src/vulkan/runtime/vk_image.h",
    "#if DETECT_OS_LINUX || DETECT_OS_BSD",
    "#if DETECT_OS_LINUX || DETECT_OS_BSD || DETECT_OS_WINDOWS")
sub("src/vulkan/runtime/vk_image.c",
    "#if DETECT_OS_LINUX || DETECT_OS_BSD\n"
    "   image->drm_format_mod = ((1ULL << 56) - 1) /* DRM_FORMAT_MOD_INVALID */;\n#endif",
    "#if DETECT_OS_LINUX || DETECT_OS_BSD || DETECT_OS_WINDOWS\n"
    "   image->drm_format_mod = ((1ULL << 56) - 1) /* DRM_FORMAT_MOD_INVALID */;\n#endif")

sub("src/panfrost/compiler/bifrost/bi_spill_ssa.c",
    "#include \"util/bitset.h\"",
    "#ifdef _WIN32\n#include <malloc.h>\n#define alloca _alloca\n#endif\n\n"
    "#include \"util/bitset.h\"")

sub("src/panfrost/vulkan/panvk_vX_shader.c",
    "#include \"poly/nir/poly_nir.h\"",
    "#include \"util/strndup.h\"\n#include \"poly/nir/poly_nir.h\"")

sub("src/util/u_math.c",
    "#elif DETECT_CC_MSVC\n      fpstate = (unsigned)_ReadStatusReg(ARM64_FPCR);",
    "#elif DETECT_CC_MSVC && !defined(__clang__) /* clang-cl: no ARM64_FPCR */\n"
    "      fpstate = (unsigned)_ReadStatusReg(ARM64_FPCR);")
sub("src/util/u_math.c",
    "#elif DETECT_CC_MSVC\n      _WriteStatusReg(ARM64_FPCR, fpstate);",
    "#elif DETECT_CC_MSVC && !defined(__clang__) /* clang-cl: no ARM64_FPCR */\n"
    "      _WriteStatusReg(ARM64_FPCR, fpstate);")

sub("src/util/os_mman.h",
    "#if DETECT_OS_POSIX\n#  include <sys/mman.h>\n#else\n#  error Unsupported OS\n#endif",
    "#if DETECT_OS_POSIX || DETECT_OS_WINDOWS\n"
    "/* Windows: sys/mman.h comes from include/win32-compat. */\n"
    "#  include <sys/mman.h>\n#else\n#  error Unsupported OS\n#endif")

sub("src/util/os_mman.h",
    "static inline int os_munmap(void *addr, size_t length)\n{\n"
    "   /* Copied from configure code generated by AC_SYS_LARGEFILE */",
    "#if DETECT_OS_WINDOWS\n"
    "static inline int os_munmap(void *addr, size_t length)\n{\n"
    "   return munmap(addr, length);\n}\n"
    "#else\n"
    "static inline int os_munmap(void *addr, size_t length)\n{\n"
    "   /* Copied from configure code generated by AC_SYS_LARGEFILE */")

sub("src/util/os_mman.h",
    "   return munmap(addr, length);\n}\n#endif\n\n\n#ifdef __cplusplus",
    "   return munmap(addr, length);\n}\n#endif\n#endif\n\n\n#ifdef __cplusplus")

sub("src/panfrost/lib/kmod/pan_kmod.h",
    "#include <unistd.h>\n#include <xf86drm.h>",
    "#include <unistd.h>\n#include <sys/mman.h>\n#include <xf86drm.h>")

# --------------------------------------------------------------------------
# kmod build: use the vdrm transport instead of the Linux virtgpu ioctls.
# --------------------------------------------------------------------------
sub("src/panfrost/lib/kmod/meson.build",
    "  libpankmod_lib_files += files('kbase_kmod.c', 'mali_kbase_virtio.c')",
    "  libpankmod_lib_files += files('kbase_kmod.c', 'mali_kbase_vdrm_win.c',\n"
    "                                'win32_stubs.c', 'vdrm/vdrm.c',\n"
    "                                'vdrm/vdrm_wddm.c')")

sub("src/panfrost/lib/kmod/meson.build",
    "  include_directories : [inc_include, inc_src, inc_panfrost],",
    "  include_directories : [inc_include, inc_src, inc_panfrost,\n"
    "                         include_directories('vdrm')],")

sub("src/panfrost/lib/kmod/meson.build",
    "  dependencies: [dep_libdrm, idep_mesautil, idep_pan_packers, libpanfrost_model_dep],",
    "  dependencies: [idep_mesautil, idep_pan_packers, libpanfrost_model_dep],")

sub("src/panfrost/lib/kmod/meson.build",
    "  dependencies: [dep_libdrm],",
    "  dependencies: [],")

# --------------------------------------------------------------------------
# PanVK: no libdrm on Windows; link the pankmod static library.
# --------------------------------------------------------------------------
sub("src/panfrost/vulkan/meson.build", "      dep_libdrm,\n", "", count=10)
sub("src/panfrost/vulkan/meson.build", "    dep_libdrm,\n", "", count=10)
sub("src/panfrost/vulkan/meson.build",
    "  link_with : [\n    libpanfrost_shared,",
    "  link_with : [\n    libpankmod_lib,\n    libpanfrost_shared,")

# --------------------------------------------------------------------------
# Instance enumeration: skip DRM on Windows, use the WDDM kbase device.
# --------------------------------------------------------------------------
wrap("src/panvk/instance.c" if (root / "src/panvk/instance.c").exists()
     else "src/panfrost/vulkan/panvk_instance.c",
     "static VkResult\npanvk_physical_device_try_create",
     "static VkResult\npanvk_enumerate_physical_devices",
     "#ifndef _WIN32\n")

sub("src/panfrost/vulkan/panvk_instance.c",
    "   /* Enumerate DRM render nodes (panfrost / panthor). */",
    "#ifndef _WIN32\n   /* Enumerate DRM render nodes (panfrost / panthor). */")

sub("src/panfrost/vulkan/panvk_instance.c",
    "#if defined(HAVE_PAN_KMOD_KBASE)\n   /* Enumerate kbase (Mali) non-DRM nodes. */",
    "#endif /* !_WIN32 */\n\n"
    "#if defined(HAVE_PAN_KMOD_KBASE)\n"
    "#ifdef _WIN32\n"
    "   /* Windows: one virtio WDDM kbase device; vdrm owns the connection. */\n"
    "   struct panvk_physical_device *device =\n"
    "      vk_zalloc(&instance->vk.alloc, sizeof(*device), 8,\n"
    "                VK_SYSTEM_ALLOCATION_SCOPE_INSTANCE);\n"
    "   if (!device)\n"
    "      return panvk_error(instance, VK_ERROR_OUT_OF_HOST_MEMORY);\n"
    "   VkResult result =\n"
    "      panvk_physical_device_init_kbase(device, instance, \"wddm\");\n"
    "   if (result != VK_SUCCESS) {\n"
    "      vk_free(&instance->vk.alloc, device);\n"
    "      return result;\n"
    "   }\n"
    "   list_addtail(&device->vk.link, &vk_instance->physical_devices.list);\n"
    "#else\n"
    "   /* Enumerate kbase (Mali) non-DRM nodes. */")

sub("src/panfrost/vulkan/panvk_instance.c",
    "      list_addtail(&device->vk.link, &vk_instance->physical_devices.list);\n"
    "   }\n#endif /* HAVE_PAN_KMOD_KBASE */\n\n   return VK_SUCCESS;\n}",
    "      list_addtail(&device->vk.link, &vk_instance->physical_devices.list);\n"
    "   }\n#endif /* !_WIN32 */\n#endif /* HAVE_PAN_KMOD_KBASE */\n\n"
    "   return VK_SUCCESS;\n}")

# --------------------------------------------------------------------------
# Physical device: open the WDDM transport without a /dev/mali node.
# --------------------------------------------------------------------------
sub("src/panfrost/vulkan/panvk_physical_device.c",
    "#include <errno.h>",
    "#include <errno.h>\n#ifdef _WIN32\n#include <io.h>\n#include <fcntl.h>\n#endif")

sub("src/panfrost/vulkan/panvk_physical_device.c",
    "   fd = open(path, O_RDWR | O_CLOEXEC);",
    "#ifdef _WIN32\n"
    "   /* vdrm owns the KMD connection; the CRT fd is only a kbv key. */\n"
    "   fd = _open(\"NUL\", _O_RDWR);\n"
    "#else\n"
    "   fd = open(path, O_RDWR | O_CLOEXEC);\n"
    "#endif")

sub("src/panfrost/vulkan/panvk_physical_device.c",
    "   configure_kbase_dvfs(path);",
    "#ifndef _WIN32\n   configure_kbase_dvfs(path);\n#endif")

sub("src/panfrost/vulkan/panvk_physical_device.c",
    "   case 6:\n   case 7:\n   case 14:\n   case 15:\n"
    "      if (!os_get_option(\"PAN_I_WANT_A_BROKEN_VULKAN_DRIVER\")) {",
    "   case 6:\n   case 7:\n   case 14:\n   case 15:\n"
    "#ifdef _WIN32\n"
    "      /* G2-Ultra (arch 15) is the validated native-context target. */\n"
    "      break;\n"
    "#endif\n"
    "      if (!os_get_option(\"PAN_I_WANT_A_BROKEN_VULKAN_DRIVER\")) {")

# The DRM-only init path is not built on Windows.  The kbase init after it is.
wrap("src/panfrost/vulkan/panvk_physical_device.c",
     "static VkResult\nget_drm_device_ids",
     "static VkResult\nget_core_mask",
     "#ifndef _WIN32\n")

wrap("src/panfrost/vulkan/panvk_physical_device.c",
     "VkResult\npanvk_physical_device_init(",
     "#if defined(HAVE_PAN_KMOD_KBASE)",
     "#ifndef _WIN32\n")

# --------------------------------------------------------------------------
# WSI: no DRM device on Windows; wsi_common still supplies the Win32/GDI
# surface.  Keep the default CPU path.
# --------------------------------------------------------------------------
wrap("src/panfrost/vulkan/panvk_wsi.c",
     "static bool\npanvk_can_present_on_device",
     "VkResult\npanvk_wsi_init",
     "#ifndef _WIN32\n")

sub("src/panfrost/vulkan/panvk_wsi.c",
    "   physical_device->wsi_device.can_present_on_device =\n"
    "      panvk_can_present_on_device;",
    "#ifndef _WIN32\n"
    "   physical_device->wsi_device.can_present_on_device =\n"
    "      panvk_can_present_on_device;\n"
    "#else\n"
    "   physical_device->wsi_device.can_present_on_device = NULL;\n"
    "#endif")

# --------------------------------------------------------------------------
# kbase_kmod: the tracking page is anonymous memory, not an mmap.
# --------------------------------------------------------------------------
sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "   void *tracking_page = virtio ? mmap(NULL, 4096, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) :\n"
    "      mmap(NULL, 4096, PROT_NONE, MAP_SHARED, fd, BASE_MEM_MAP_TRACKING_HANDLE);\n"
    "   if (tracking_page == MAP_FAILED) {",
    "#ifdef _WIN32\n"
    "   void *tracking_page = virtio ? calloc(1, 4096) : MAP_FAILED;\n"
    "   if (!tracking_page) {\n"
    "#else\n"
    "   void *tracking_page = virtio ? mmap(NULL, 4096, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) :\n"
    "      mmap(NULL, 4096, PROT_NONE, MAP_SHARED, fd, BASE_MEM_MAP_TRACKING_HANDLE);\n"
    "   if (tracking_page == MAP_FAILED) {\n"
    "#endif")

sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "munmap(tracking_page, 4096)", "free(tracking_page)", count=10)

# --------------------------------------------------------------------------
# A Windows drmDevicePtr forward declaration for the DRM-only prototypes.
# --------------------------------------------------------------------------
sub("include/win32-compat/xf86drm.h",
    "#include <stdint.h>",
    "#include <stdint.h>\n\n#ifndef _WIN32_DRM_DEVICE_PTR\n"
    "#define _WIN32_DRM_DEVICE_PTR\ntypedef struct _drmDevice *drmDevicePtr;\n#endif")

sub("src/panfrost/vulkan/panvk_physical_device.h",
    "#include <stdint.h>\n#include <sys/types.h>",
    "#include <stdint.h>\n#include <sys/types.h>\n"
    "#ifdef _WIN32\n#ifndef _WIN32_DRM_DEVICE_PTR\n"
    "#define _WIN32_DRM_DEVICE_PTR\n"
    "typedef struct _drmDevice *drmDevicePtr;\n#endif\n#endif")

# kbase_kmod's dma-buf duplicate path uses POSIX fcntl; MSVC has _dup.
sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "#include <fcntl.h>",
    "#include <fcntl.h>\n#ifdef _WIN32\n#include <io.h>\n#endif")
sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "fcntl(fd, F_DUPFD_CLOEXEC, 3)", "_dup(fd)")
sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "fcntl(kbase_bo->dmabuf_fd, F_DUPFD_CLOEXEC, 3)",
    "_dup(kbase_bo->dmabuf_fd)")
sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "fcntl(fd, F_DUPFD_CLOEXEC, 0)", "_dup(fd)")

print(f"patch_mesa: {changes} edits applied, {len(misses)} anchors missing")
for m in misses:
    print("  MISS:", m)
sys.exit(0 if not misses else 2)
