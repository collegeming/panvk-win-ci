/* SPDX-License-Identifier: MIT
 * Minimal sched.h for the Windows ARM64 Mesa build. */
#pragma once
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
static inline int sched_yield(void)
{
   SwitchToThread();
   return 0;
}
