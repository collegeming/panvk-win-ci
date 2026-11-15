/* SPDX-License-Identifier: GPL-2.0 */
/* Mesa's drm-uapi/mali_kbase_ioctl.h includes <linux/ioctl.h>; the Windows
 * shim only needs the BSD-style request encoding in sys/ioctl.h. */
#pragma once
#include <sys/ioctl.h>
