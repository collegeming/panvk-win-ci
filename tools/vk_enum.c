/* SPDX-License-Identifier: MIT
 * Loader-free Vulkan enumeration/create-device smoke test for the ARM64
 * PanVK ICD.  Loads vulkan_virtio.dll directly, calls
 * vk_icdGetInstanceProcAddr, enumerates physical devices and creates a
 * device on the first queue family.  No Vulkan loader is required.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <vulkan/vulkan_core.h>

typedef PFN_vkVoidFunction(VKAPI_PTR *PFN_icd_gipa)(VkInstance, const char *);

static PFN_icd_gipa g_icd_gipa;

static PFN_vkVoidFunction
gipa(VkInstance instance, const char *name)
{
   return g_icd_gipa(instance, name);
}

static const char *
vkres(VkResult r)
{
   switch (r) {
   case VK_SUCCESS: return "VK_SUCCESS";
   case VK_ERROR_OUT_OF_HOST_MEMORY: return "VK_ERROR_OUT_OF_HOST_MEMORY";
   case VK_ERROR_OUT_OF_DEVICE_MEMORY: return "VK_ERROR_OUT_OF_DEVICE_MEMORY";
   case VK_ERROR_INITIALIZATION_FAILED: return "VK_ERROR_INITIALIZATION_FAILED";
   case VK_ERROR_DEVICE_LOST: return "VK_ERROR_DEVICE_LOST";
   case VK_ERROR_EXTENSION_NOT_PRESENT: return "VK_ERROR_EXTENSION_NOT_PRESENT";
   case VK_ERROR_FEATURE_NOT_PRESENT: return "VK_ERROR_FEATURE_NOT_PRESENT";
   case VK_ERROR_INCOMPATIBLE_DRIVER: return "VK_ERROR_INCOMPATIBLE_DRIVER";
   default: return "VK_ERROR_OTHER";
   }
}

int
main(int argc, char **argv)
{
   const char *dll = argc > 1 ? argv[1] : "vulkan_virtio.dll";
   HMODULE mod = LoadLibraryA(dll);
   if (!mod) {
      printf("LoadLibrary(%s) failed: %lu\n", dll, (unsigned long)GetLastError());
      return 1;
   }
   g_icd_gipa = (PFN_icd_gipa)(void *)GetProcAddress(mod, "vk_icdGetInstanceProcAddr");
   if (!g_icd_gipa) {
      printf("%s lacks vk_icdGetInstanceProcAddr\n", dll);
      return 1;
   }
   printf("ICD loaded: %s\n", dll);

   PFN_vkCreateInstance create_instance =
      (PFN_vkCreateInstance)(void *)gipa(NULL, "vkCreateInstance");
   PFN_vkEnumerateInstanceExtensionProperties enum_ext =
      (PFN_vkEnumerateInstanceExtensionProperties)(void *)gipa(NULL, "vkEnumerateInstanceExtensionProperties");
   if (!create_instance || !enum_ext) {
      printf("vkCreateInstance / vkEnumerateInstanceExtensionProperties missing\n");
      return 1;
   }

   uint32_t ext_count = 0;
   VkResult r = enum_ext(NULL, &ext_count, NULL);
   printf("instance extensions: result=%d (%s) count=%u\n", r, vkres(r), ext_count);
   if (r == VK_SUCCESS && ext_count) {
      VkExtensionProperties *ext = calloc(ext_count, sizeof(*ext));
      if (ext && enum_ext(NULL, &ext_count, ext) == VK_SUCCESS) {
         for (uint32_t i = 0; i < ext_count; i++)
            printf("  ext[%u] %s\n", i, ext[i].extensionName);
      }
      free(ext);
   }

   VkApplicationInfo app = {
      .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
      .pApplicationName = "panvk-win-probe",
      .applicationVersion = 1,
      .pEngineName = "none",
      .engineVersion = 1,
      .apiVersion = VK_MAKE_API_VERSION(0, 1, 3, 0),
   };
   VkInstanceCreateInfo ici = {
      .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
      .pApplicationInfo = &app,
   };
   VkInstance instance = VK_NULL_HANDLE;
   r = create_instance(&ici, NULL, &instance);
   printf("vkCreateInstance: result=%d (%s) instance=%p\n", r, vkres(r), (void *)instance);
   if (r != VK_SUCCESS)
      return 1;

   PFN_vkEnumeratePhysicalDevices enum_pd =
      (PFN_vkEnumeratePhysicalDevices)(void *)gipa(instance, "vkEnumeratePhysicalDevices");
   PFN_vkGetPhysicalDeviceProperties get_props =
      (PFN_vkGetPhysicalDeviceProperties)(void *)gipa(instance, "vkGetPhysicalDeviceProperties");
   PFN_vkGetPhysicalDeviceQueueFamilyProperties get_qf =
      (PFN_vkGetPhysicalDeviceQueueFamilyProperties)(void *)gipa(instance, "vkGetPhysicalDeviceQueueFamilyProperties");
   PFN_vkCreateDevice create_device =
      (PFN_vkCreateDevice)(void *)gipa(instance, "vkCreateDevice");
   PFN_vkDestroyDevice destroy_device =
      (PFN_vkDestroyDevice)(void *)gipa(instance, "vkDestroyDevice");
   if (!enum_pd || !get_props || !get_qf || !create_device) {
      printf("physical-device entry points missing\n");
      return 1;
   }

   uint32_t pd_count = 0;
   r = enum_pd(instance, &pd_count, NULL);
   printf("vkEnumeratePhysicalDevices(count): result=%d (%s) count=%u\n", r, vkres(r), pd_count);
   if (r != VK_SUCCESS || !pd_count)
      return 1;
   VkPhysicalDevice *pds = calloc(pd_count, sizeof(*pds));
   r = enum_pd(instance, &pd_count, pds);
   printf("vkEnumeratePhysicalDevices(list): result=%d (%s) count=%u\n", r, vkres(r), pd_count);
   if (r != VK_SUCCESS && r != VK_INCOMPLETE)
      return 1;

   int rc = 0;
   for (uint32_t i = 0; i < pd_count; i++) {
      VkPhysicalDeviceProperties props;
      memset(&props, 0, sizeof(props));
      get_props(pds[i], &props);
      printf("physical_device[%u]: %s api=%u.%u.%u vendor=0x%04x device=0x%04x type=%d\n",
             i, props.deviceName,
             VK_API_VERSION_MAJOR(props.apiVersion),
             VK_API_VERSION_MINOR(props.apiVersion),
             VK_API_VERSION_PATCH(props.apiVersion),
             props.vendorID, props.deviceID, (int)props.deviceType);

      uint32_t qf_count = 0;
      get_qf(pds[i], &qf_count, NULL);
      VkQueueFamilyProperties *qf = calloc(qf_count ? qf_count : 1, sizeof(*qf));
      if (qf_count)
         get_qf(pds[i], &qf_count, qf);
      uint32_t qfi = UINT32_MAX;
      for (uint32_t q = 0; q < qf_count; q++) {
         printf("  queue_family[%u]: count=%u flags=0x%x\n", q, qf[q].queueCount, qf[q].queueFlags);
         if (qfi == UINT32_MAX && qf[q].queueCount)
            qfi = q;
      }
      free(qf);
      if (qfi == UINT32_MAX) {
         printf("  no queue family\n");
         rc = 1;
         continue;
      }

      float priority = 1.0f;
      VkDeviceQueueCreateInfo qci = {
         .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
         .queueFamilyIndex = qfi,
         .queueCount = 1,
         .pQueuePriorities = &priority,
      };
      VkDeviceCreateInfo dci = {
         .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
         .queueCreateInfoCount = 1,
         .pQueueCreateInfos = &qci,
      };
      VkDevice device = VK_NULL_HANDLE;
      r = create_device(pds[i], &dci, NULL, &device);
      printf("  vkCreateDevice(queue_family=%u): result=%d (%s) device=%p\n",
             qfi, r, vkres(r), (void *)device);
      if (r == VK_SUCCESS && destroy_device)
         destroy_device(device, NULL);
      else if (r != VK_SUCCESS)
         rc = 1;
   }

   free(pds);
   return rc;
}
