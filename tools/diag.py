#!/usr/bin/env python3
"""Temporary M2 diagnostic inserts for the Windows PanVK ICD."""
import sys
from pathlib import Path

root = Path(sys.argv[1])
edits = 0

def ins(rel, old, new):
    global edits
    p = root / rel
    s = p.read_text(encoding="utf-8", errors="surrogateescape")
    if old not in s:
        print("DIAG MISS", rel, old[:60])
        return
    p.write_text(s.replace(old, new, 1), encoding="utf-8", errors="surrogateescape")
    edits += 1

ins("src/panfrost/vulkan/panvk_instance.c",
    "#ifndef _WIN32\n   /* Enumerate DRM render nodes (panfrost / panthor). */",
    "   fprintf(stderr, \"win-panvk: enumerate enter\\n\");\n"
    "#ifndef _WIN32\n   /* Enumerate DRM render nodes (panfrost / panthor). */")

ins("src/panfrost/vulkan/panvk_instance.c",
    "#ifdef _WIN32\n   /* Windows: one virtio WDDM kbase device;",
    "#ifdef _WIN32\n   fprintf(stderr, \"win-panvk: windows kbase branch\\n\");\n"
    "   /* Windows: one virtio WDDM kbase device;")

ins("src/panfrost/vulkan/panvk_physical_device.c",
    "create_kmod_dev_kbase(struct panvk_physical_device *device,\n"
    "                      const struct panvk_instance *instance,\n"
    "                      const char *path)\n{\n   int fd;",
    "create_kmod_dev_kbase(struct panvk_physical_device *device,\n"
    "                      const struct panvk_instance *instance,\n"
    "                      const char *path)\n{\n"
    "   fprintf(stderr, \"win-panvk: create_kmod_dev_kbase path=%s\\n\", path);\n"
    "   int fd;")

ins("src/panfrost/lib/kmod/mali_kbase_vdrm_win.c",
    "   struct vdrm_device *vdev = vdrm_device_connect(-1, KBV_CONTEXT_TYPE);",
    "   fprintf(stderr, \"win-panvk: kbv_init connect begin\\n\");\n"
    "   struct vdrm_device *vdev = vdrm_device_connect(-1, KBV_CONTEXT_TYPE);\n"
    "   fprintf(stderr, \"win-panvk: kbv_init vdev=%p\\n\", (void *)vdev);")

ins("src/panfrost/lib/kmod/vdrm/vdrm_wddm.c",
    "vdrm_wddm_connect(int fd, uint32_t context_type)\n{",
    "vdrm_wddm_connect(int fd, uint32_t context_type)\n{\n"
    "   fprintf(stderr, \"win-panvk: vdrm_wddm_connect enter context=0x%x\\n\", context_type);")

ins("src/panfrost/lib/kmod/vdrm/vdrm_wddm.c",
    "      WDDM_DEBUG(\"connect failed at %s\\n\", stage);",
    "      fprintf(stderr, \"win-panvk: vdrm_wddm_connect failed at %s\\n\", stage);\n"
    "      WDDM_DEBUG(\"connect failed at %s\\n\", stage);")

ins("src/panfrost/vulkan/panvk_physical_device.c",
    "   fd = _open(\"NUL\", _O_RDWR);",
    "   fd = _open(\"NUL\", _O_RDWR);\n"
    "   fprintf(stderr, \"win-panvk: _open NUL fd=%d errno=%d\n\", fd, errno);")

ins("src/panfrost/vulkan/panvk_physical_device.c",
    "   device->kmod.dev = pan_kmod_dev_create_with_driver(fd, flags, \"kbase\", NULL,",
    "   fprintf(stderr, \"win-panvk: pan_kmod_dev_create begin fd=%d flags=0x%x\n\", fd, flags);\n"
    "   device->kmod.dev = pan_kmod_dev_create_with_driver(fd, flags, \"kbase\", NULL,")

ins("src/panfrost/vulkan/panvk_physical_device.c",
    "      return panvk_errorf(instance, VK_ERROR_INCOMPATIBLE_DRIVER,\n"
    "                          \"failed to create kbase device at %s\", path);",
    "      fprintf(stderr, \"win-panvk: pan_kmod_dev_create failed errno=%d\n\", errno);\n"
    "      return panvk_errorf(instance, VK_ERROR_INCOMPATIBLE_DRIVER,\n"
    "                          \"failed to create kbase device at %s\", path);")

ins("src/panfrost/lib/kmod/kbase_kmod.c",
    "kbase_kmod_dev_create(int fd, uint32_t flags,",
    "kbase_kmod_dev_create(int fd, uint32_t flags,")

ins("src/panfrost/lib/kmod/kbase_kmod.c",
    "   struct kbase_ioctl_version_check ver = { 0 };",
    "   fprintf(stderr, \"win-panvk: kbase_kmod_dev_create fd=%d\n\", fd);\n"
    "   struct kbase_ioctl_version_check ver = { 0 };")

print(f"diag: {edits} edits")
