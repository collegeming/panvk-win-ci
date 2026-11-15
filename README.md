# panvk-win-ci

Build-only candidate for a Windows ARM64 PanVK ICD for the DroidVM virtio
WDDM KMD (`virtio_wddm_rs.sys`) on Mali-G2-Ultra-NX (kbase r56p0).

The host side (crosvm `context-types=virgl2:drm` + virglrenderer
`mali_kbase`) and the Windows KMD/UMD stack are already validated by
`collegeming/win-panvk-probe` (M1: capset 6 KBAS, props 781 B, CSIF 24 B,
two rounds PASS). This repo is the M2 build: manet Mesa 26.3 PanVK (the
only branch with G2-Ultra support) plus the `vdrm` WDDM transport.

Contents:

- `vendor/mesa-patches/`: GPL-2.0 Windows/Panfrost portability patches from
  `gahingwoo/wddm-mali-g52` (attribution in `vendor/NOTICE`).
- `vendor/win32-compat/`: POSIX/Panfrost shims from the same source.
- `src/vdrm/`: MIT vdrm sources from `collegeming/win-panvk-probe`.
- `src/mali_kbase_vdrm_win.c`: kbv RPC over vdrm for PanVK.
- `.github/workflows/build.yml`: Linux libpan prebuild + Windows ARM64
  PanVK build.

This repository contains no device credentials and is build-only.
