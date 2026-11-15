/* SPDX-License-Identifier: MIT
 * v15 ray-tracing stubs for the Windows M2 build.
 *
 * The Windows build disables the BVH/glslang ray-tracing sources.  Arch 15
 * device init/finish still reference these four symbols, so provide safe
 * no-ops.  Ray-tracing pipelines are expected to fail cleanly; M2 only
 * targets enumeration and vkCreateDevice.
 */
#include <stdint.h>
#include <vulkan/vulkan_core.h>

struct panvk_device;
struct nir_shader;

void
panvk_v15_device_init_accel_struct(struct panvk_device *dev)
{
   (void)dev;
}

VkResult
panvk_v15_device_reserve_ray_query_slots(struct panvk_device *dev,
                                         uint32_t slots)
{
   (void)dev; (void)slots;
   return VK_ERROR_FEATURE_NOT_PRESENT;
}

void
panvk_v15_device_finish_ray_query(struct panvk_device *dev)
{
   (void)dev;
}

uint32_t
panvk_v15_nir_lower_ray_queries(struct nir_shader *nir)
{
   (void)nir;
   return 0;
}
