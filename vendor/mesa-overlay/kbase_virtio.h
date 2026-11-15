/* SPDX-License-Identifier: MIT
 * Manet's PanVK source includes "kmod/kbase_virtio.h" in two files, but the
 * branch ships the declarations as mali_kbase_virtio.h.  This forwarding
 * header keeps those includes working; the implementation is
 * mali_kbase_vdrm_win.c. */
#pragma once
#include "mali_kbase_virtio.h"
