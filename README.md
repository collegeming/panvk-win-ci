# panvk-win-ci (M2)

Windows 11 ARM64 PanVK ICD for the DroidVM virtio WDDM KMD
(`virtio_wddm_rs.sys`) on Mali-G2-Ultra-NX (kbase r56p0).

M1 (`collegeming/win-panvk-probe`) 已验证 KMD + vdrm + host mali_kbase：
capset6 `KBAS`、props 781 B、CSIF 24 B、两轮 connect/teardown PASS。
本仓库把同一 `vdrm`/kbv RPC 接到 manet Mesa 26.3 PanVK，产出 ARM64
`vulkan_manet.dll`（复制为 `vulkan_virtio.dll` 供 dx11um_virtio 回退加载）。

## 当前状态（2026-11-15）

- GitHub Actions run `43732284937`（`mesa-panvk-win32`）成功。
- Artifact `mesa-panvk-win32` 内容：

| 文件 | 说明 |
| --- | --- |
| `out/vulkan_manet.dll` | ARM64 PanVK ICD，PE machine `0xAA64` |
| `out/vulkan_virtio.dll` | 同一文件，供 UMD 按 `vulkan_virtio.dll` 加载 |
| `out/vcruntime140.dll` | ARM64 VC 运行库（客机缺 VCRUNTIME140 时使用） |
| `out/vulkan_virtio_icd.json` | `VK_DRIVER_FILES` 用，`library_path=./vulkan_virtio.dll` |
| `out/manet_icd.json` | Mesa 原始 manifest（路径是构建树相对路径） |
| `out/vk_enum.exe` | loader-free 枚举/CreateDevice 冒烟程序 |
| `out/vk_enum.out` | runner 上的运行输出 |
| `out/SHA256SUMS.txt` | DLL 与 vcruntime 的 SHA256 |
| `out/exports.txt` | `llvm-readobj --file-headers --coff-exports` 输出 |
| `build.log` | 完整 ninja 日志 |

`vulkan_virtio.dll` SHA256：

```
1028AC776E9789253759E84C09D08C82CC2BE33891E03DAF87121B8181FAEE7F
```

`vcruntime140.dll` SHA256：

```
3C56F4167E2B3D8E6338497731E6AAE8CD7EC46BD6789F9423A8D9CF9A630310
```

runner 上的 loader-free 冒烟结果（无 virtio 适配器，因此 0 设备）：

```
ICD loaded: ...\vulkan_manet.dll
instance extensions: result=0 (VK_SUCCESS) count=7
vkCreateInstance: result=0 (VK_SUCCESS)
vkEnumeratePhysicalDevices(count): result=0 (VK_SUCCESS) count=0
[panvk-win] enumerate: Windows kbase branch, HAVE_PAN_KMOD_KBASE=1
[panvk-win] create_kmod_dev_kbase path=wddm
[panvk-win] _open(NUL) fd=3 errno=0
[panvk-win] calling pan_kmod_dev_create_with_driver("kbase") fd=3 flags=0x1
[kbv-win] kbv_init fd=3: calling vdrm_device_connect(type=0x4b424153)
[vdrm-wddm] connect entry: fd=-1 context_type=0x4b424153
[vdrm-wddm] dispatch_init ok
[vdrm-wddm] EnumAdapters2(count): status=0x00000000 num_adapters=34
[vdrm-wddm] EnumAdapters2(list): status=0x00000000 num_adapters=2
[vdrm-wddm] adapter[0]: ... tag=0x0000320000000002 ... match=0
[vdrm-wddm] adapter[1]: ... tag=0x0000320000000002 ... match=0
[vdrm-wddm] no virtio WDDM adapter found (tag=0x464e495041444156)
[vdrm-wddm] connect failed at stage 'adapter enumeration'
```

runner 没有 virtio WDDM 适配器，所以最后停在 adapter enumeration 是预期；
客机上应能命中 `VADAPINF` 并继续到 ContextInit / props / CSIF。

导出表确认包含：

```
vk_icdGetInstanceProcAddr
vk_icdGetPhysicalDeviceProcAddr
vk_icdNegotiateLoaderICDInterfaceVersion
vk_icdEnumerateAdapterPhysicalDevices
```

## 构建管线

`.github/workflows/build.yml`：

1. Linux `libpan` job（默认跳过，复用 run `43720536739` 的 artifact）：
   Mesa 26.3 配置 `-Dvulkan-drivers=panfrost -Dpanfrost-kmds=panfrost`，
   生成 `libpan_v*.spv/.cpp/.h`、`libpan_shaders_v*` 与 `libpoly.*`。
2. Windows `windows-11-arm` job：
   - 克隆 `MollySophia/mesa-manet` 分支 `feature/mali-kbase-native-context`；
   - 复制 `vendor/win32-compat`（POSIX/libdrm/d3d 兼容头）与
     `vendor/mesa-overlay`（`kbase_virtio.h` 转发、v15 RT 桩、ICD `.def`）；
   - `tools/patch_mesa.py` 做 Windows/PanVK 移植编辑（枚举、kbase init、
     DRM 路径裁剪、Windows 头/ELF build-id/syncobj 桩、v15-only 编译）；
   - 预置 `libpan`/`libpoly`，`meson setup` + `ninja`；
   - 打包 `vulkan_virtio.dll`、ICD JSON、SHA256、导出表并上传 artifact。

工具链：VS2026 ARM64 `clang-cl`、Windows SDK 10.0.26100（无需 WDK）、
Meson/Ninja、winflexbison、clang-cl `/MD`。

## 客机验证

把 artifact 解压到例如 `C:\panvk\`，然后：

```bat
C:\panvk\vk_enum.exe C:\panvk\vulkan_virtio.dll
```

期望在真实客机上看到 1 个 `Mali G2-Ultra` 设备、`vkCreateDevice` 返回
`VK_SUCCESS`。也可以走 Vulkan loader：

```bat
set VK_DRIVER_FILES=C:\panvk\vulkan_virtio_icd.json
set VK_LOADER_DEBUG=error,warn
set PANVK_DEBUG=startup
vulkaninfo --summary
```

或直接让 D3D11 UMD 回退：把 `vulkan_virtio.dll` 放到
`dx11um_virtio.dll` 的搜索路径（同目录/System32 需按现有部署方式），
运行 D3D11 offscreen 冒烟程序。最小判据：

- `vkEnumeratePhysicalDevices` 返回 1 个设备；
- 设备名含 `Mali G2` / `Mali unknown`（取决于 model 表命中）；
- `vkCreateDevice` 返回 `VK_SUCCESS`。

调试：`PANVK_DEBUG=startup,dbg`（可选），`VK_LOADER_DEBUG=all`；宿主侧
crosvm/virglrenderer 应出现与 M1 一致的 `mali-create`/`mali-props` 日志。

## 已知限制（M2，实验性）

- `vendor/mesa-patches` 里 wddm-mali-g52 的 Mesa 26.2 补丁只有部分能应用到
  manet 26.3；**`0003`（Bifrost 位域可移植打包）和 `0011`（enum 位域
  unsigned）当前被跳过**。枚举/vkCreateDevice 不受影响，但真实渲染的 GPU
  指令/纹理描述符编码尚未验证；上屏/游戏前必须 rebase 这两个补丁。
- WSI：Win32 surface 扩展尚未在 `panvk_instance` 扩展表注册；
  `vulkan_virtio_icd.json` 适合 headless/offscreen。GDI DIB present 路径
  留到下一里程碑。
- RT/BVH 源被关闭，v15 RT 入口是安全桩；async-bind DRM syncobj 与
  `vk_drm_syncobj_*` 也是失败桩。
- `pan_trace` 的 Android `_Unwind_*` 回溯在 Windows 返回空栈。
- DLL 未签名；客机需按现有测试签名/允许策略加载，不要关闭系统安全策略。
- 仅 ARM64；x64/x86 未构建。

## 许可与来源

- Mesa / vdrm：MIT（见 `vendor/NOTICE`、`src/vdrm`）。
- `vendor/mesa-patches`、`vendor/win32-compat`：来自 GPL-2.0 的
  `gahingwoo/wddm-mali-g52`（仅本实验使用）。
- KMD UAPI / virtio-d3d11 头：AGPL-3.0（仅私有实验，不再分发）。
- 本仓库其余脚本与 overlay：MIT。
