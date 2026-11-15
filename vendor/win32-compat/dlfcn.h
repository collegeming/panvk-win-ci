/* SPDX-License-Identifier: MIT
 * Minimal dlfcn.h for the Windows ARM64 Mesa build.  PanVK's trace helper
 * asks dladdr() for a symbol name; returning 0 makes it use its fallback. */
#pragma once
#define RTLD_LAZY 0
#define RTLD_NOW 0
typedef struct {
   const char *dli_fname;
   void *dli_fbase;
   const char *dli_sname;
   void *dli_saddr;
} Dl_info;
static inline void *dlopen(const char *file, int mode)
{
   (void)file; (void)mode;
   return 0;
}
static inline void *dlsym(void *handle, const char *name)
{
   (void)handle; (void)name;
   return 0;
}
static inline int dlclose(void *handle)
{
   (void)handle;
   return 0;
}
static inline char *dlerror(void)
{
   return 0;
}
static inline int dladdr(const void *addr, Dl_info *info)
{
   (void)addr; (void)info;
   return 0;
}
