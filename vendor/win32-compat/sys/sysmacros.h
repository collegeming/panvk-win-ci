/* SPDX-License-Identifier: MIT
 * Minimal sys/sysmacros.h for the Windows ARM64 Mesa build.  PanVK only uses
 * these to derive DRM render/primary device ids for WSI matching; on Windows
 * the kbase/vdrm path leaves them unused, so the encoding is just a stub. */
#pragma once
#define major(dev) ((unsigned)(((dev) >> 8) & 0xfffu))
#define minor(dev) ((unsigned)((dev) & 0xffu))
#define makedev(ma, mi) ((((unsigned)(ma)) << 8) | ((unsigned)(mi)))
