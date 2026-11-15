#!/usr/bin/env python3
"""Apply the Windows PanVK transport/build edits to a manet Mesa tree.

The edits are intentionally string based: the manet branch is a moving
development fork and a context patch would rot faster than these few
well-delimited changes.  Every missing anchor is reported; the CI build then
shows the real error.
"""
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "mesa")
changes = 0
misses = []


def sub(rel, old, new, count=1, required=True):
    global changes
    p = root / rel
    if not p.exists():
        misses.append(f"{rel}: file missing")
        return False
    s = p.read_text(encoding="utf-8", errors="surrogateescape")
    if old not in s:
        misses.append(f"{rel}: anchor missing: {old[:70]!r}")
        return False
    s = s.replace(old, new, count)
    p.write_text(s, encoding="utf-8", errors="surrogateescape")
    changes += 1
    return True


def wrap(rel, start_marker, end_marker, before):
    global changes
    p = root / rel
    if not p.exists():
        misses.append(f"{rel}: file missing")
        return False
    s = p.read_text(encoding="utf-8", errors="surrogateescape")
    a = s.find(start_marker)
    b = s.find(end_marker, a + 1)
    if a < 0 or b < 0:
        misses.append(f"{rel}: wrap markers missing")
        return False
    s = s[:a] + before + s[a:b] + "#endif\n\n" + s[b:]
    p.write_text(s, encoding="utf-8", errors="surrogateescape")
    changes += 1
    return True


def create(rel, content):
    """Create a file that must not exist yet.  A different existing file is a
    hard miss: it means the Mesa branch grew its own version and the patch
    below needs review instead of being silently shadowed."""
    global changes
    p = root / rel
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="surrogateescape")
        if old == content:
            return True
        misses.append(f"{rel}: exists with unexpected content")
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8", errors="surrogateescape")
    changes += 1
    return True


def require(rel, needle, why):
    """Assert a property that the Mesa branch is expected to provide already.
    Used for hunks that are upstream now: if the property disappears, fail
    the build instead of silently losing the fix."""
    p = root / rel
    if not p.exists():
        misses.append(f"{rel}: file missing")
        return False
    s = p.read_text(encoding="utf-8", errors="surrogateescape")
    if needle not in s:
        misses.append(f"{rel}: required property missing ({why}): {needle[:70]!r}")
        return False
    return True


# --------------------------------------------------------------------------
# Windows header shadow tree (POSIX/libdrm stand-ins).
# --------------------------------------------------------------------------
sub("include/meson.build",
    "inc_include = [include_directories('.')]",
    "inc_include = [include_directories('.'), include_directories('win32-compat')]")

# --------------------------------------------------------------------------
# Windows M2: no glslang/BVH ray-tracing build, and only the G2-Ultra (v15)
# per-arch PanVK library.  Both cut unrelated tool and compile surface.
# --------------------------------------------------------------------------
sub("meson.build",
    "with_bvh = with_amd_vk or with_intel_vk or with_swrast_vk or with_freedreno_vk or with_panfrost_vk",
    "with_bvh = (with_amd_vk or with_intel_vk or with_swrast_vk or with_freedreno_vk or with_panfrost_vk) and host_machine.system() != 'windows'")

sub("src/panfrost/vulkan/meson.build",
    "subdir('bvh')\n\nrt_archs = [15]",
    "if host_machine.system() != 'windows'\n"
    "  subdir('bvh')\n"
    "  rt_archs = [15]\n"
    "else\n"
    "  panvk_bvh_spv = []\n"
    "  rt_archs = []\n"
    "endif")

sub("src/panfrost/vulkan/meson.build",
    "  link_args : [vulkan_icd_link_args, ld_args_bsymbolic, ld_args_gc_sections, ld_args_build_id],",
    "  vs_module_defs : 'vulkan_manet.def',\n"
    "  link_args : [vulkan_icd_link_args, ld_args_bsymbolic, ld_args_gc_sections, ld_args_build_id],")

sub("src/panfrost/vulkan/meson.build",
    "  [libpanvk_files, panvk_entrypoints, panvk_tracepoints, panvk_drirc],",
    "  [libpanvk_files, panvk_entrypoints, panvk_tracepoints, panvk_drirc,\n"
    "   files('panvk_win_rt_stubs.c')],")

sub("src/panfrost/vulkan/meson.build",
    "foreach arch : [6, 7, 10, 11, 12, 13, 14, 15]",
    "foreach arch : [15]")

sub("src/panfrost/vulkan/meson.build",
    "    '--device-prefix', 'panvk_v6', '--device-prefix', 'panvk_v7',\n"
    "    '--device-prefix', 'panvk_v9', '--device-prefix', 'panvk_v10',\n"
    "    '--device-prefix', 'panvk_v11', '--device-prefix', 'panvk_v12',\n"
    "    '--device-prefix', 'panvk_v13', '--device-prefix', 'panvk_v14',\n"
    "    '--device-prefix', 'panvk_v15',\n",
    "    '--device-prefix', 'panvk_v15',\n")

sub("src/panfrost/vulkan/panvk_macros.h",
    "#else\n#error \"Unsupported arch\"\n#endif\n#endif\n\n#endif\n",
    "#else\n#error \"Unsupported arch\"\n#endif\n#endif\n\n"
    "#ifdef _WIN32\n"
    "/* M2 targets only Mali-G2-Ultra (v15); the other per-arch libraries are\n"
    " * not built on Windows, so resolve every dispatch to v15. */\n"
    "#undef panvk_arch_dispatch\n"
    "#undef panvk_arch_dispatch_ret\n"
    "#define panvk_arch_dispatch(arch, name, ...) \\\n"
    "   do { (void)(arch); panvk_arch_name(name, v15)(__VA_ARGS__); } while (0)\n"
    "#define panvk_arch_dispatch_ret(arch, name, ret, ...) \\\n"
    "   do { (void)(arch); ret = panvk_arch_name(name, v15)(__VA_ARGS__); } while (0)\n"
    "#endif\n\n"
    "#endif\n")

# --------------------------------------------------------------------------
# Windows portability: MSVC/clang-cl ABI and POSIX shims.
# --------------------------------------------------------------------------
sub("src/vulkan/runtime/vk_image.h",
    "#if DETECT_OS_LINUX || DETECT_OS_BSD",
    "#if DETECT_OS_LINUX || DETECT_OS_BSD || DETECT_OS_WINDOWS")
sub("src/vulkan/runtime/vk_image.c",
    "#if DETECT_OS_LINUX || DETECT_OS_BSD\n"
    "   image->drm_format_mod = ((1ULL << 56) - 1) /* DRM_FORMAT_MOD_INVALID */;\n#endif",
    "#if DETECT_OS_LINUX || DETECT_OS_BSD || DETECT_OS_WINDOWS\n"
    "   image->drm_format_mod = ((1ULL << 56) - 1) /* DRM_FORMAT_MOD_INVALID */;\n#endif")

sub("src/panfrost/compiler/bifrost/bi_spill_ssa.c",
    "#include \"util/bitset.h\"",
    "#ifdef _WIN32\n#include <malloc.h>\n#define alloca _alloca\n#endif\n\n"
    "#include \"util/bitset.h\"")

sub("src/panfrost/lib/pan_trace.c",
    "#include <string.h>",
    "#include <string.h>\n#ifdef _WIN32\n#define strncasecmp _strnicmp\n#endif")

sub("src/panfrost/vulkan/panvk_physical_device.c",
    "#include <sys/sysinfo.h>",
    "#ifndef _WIN32\n#include <sys/sysinfo.h>\n#endif")
sub("src/panfrost/vulkan/panvk_physical_device.c",
    "#include <linux/sync_file.h>",
    "#ifndef _WIN32\n#include <linux/sync_file.h>\n#endif")

sub("src/panfrost/vulkan/panvk_vX_shader.c",
    "#include \"poly/nir/poly_nir.h\"",
    "#include \"util/strndup.h\"\n#include \"poly/nir/poly_nir.h\"")

sub("src/poly/geometry.h",
    "#include \"util/u_math.h\"",
    "#include \"util/u_math.h\"\n\n#ifdef _WIN32\ntypedef unsigned int uint;\n#endif")

sub("src/panfrost/vulkan/panvk_instance.c",
    "#include \"util/build_id.h\"",
    "#include \"util/build_id.h\"\n#ifdef _WIN32\n#include <string.h>\n"
    "#if !defined(HAVE_PAN_KMOD_KBASE)\n"
    "#error \"Windows PanVK enumeration requires HAVE_PAN_KMOD_KBASE\"\n"
    "#endif\n#endif")

# ELF build-id is Linux-only; Windows has no note to hash.
build_id_block = (
    "   const struct build_id_note *note =\n"
    "      build_id_find_nhdr_for_addr(panvk_CreateInstance);\n"
    "   if (!note) {\n"
    "      return panvk_errorf(NULL, VK_ERROR_INITIALIZATION_FAILED,\n"
    "                          \"Failed to find build-id\");\n"
    "   }\n\n"
    "   unsigned build_id_len = build_id_length(note);\n"
    "   if (build_id_len < BUILD_ID_EXPECTED_HASH_LENGTH) {\n"
    "      return panvk_errorf(NULL, VK_ERROR_INITIALIZATION_FAILED,\n"
    "                          \"build-id too short.  It needs to be a SHA\");\n"
    "   }\n")
sub("src/panfrost/vulkan/panvk_instance.c", build_id_block,
    "#ifndef _WIN32\n" + build_id_block + "#endif\n")
sub("src/panfrost/vulkan/panvk_instance.c",
    "   copy_build_id_to_sha1(instance->driver_build_sha, note);",
    "#ifdef _WIN32\n"
    "   memset(instance->driver_build_sha, 0, sizeof(instance->driver_build_sha));\n"
    "#else\n"
    "   copy_build_id_to_sha1(instance->driver_build_sha, note);\n"
    "#endif")

sub("src/util/u_math.c",
    "#elif DETECT_CC_MSVC\n      fpstate = (unsigned)_ReadStatusReg(ARM64_FPCR);",
    "#elif DETECT_CC_MSVC && !defined(__clang__) /* clang-cl: no ARM64_FPCR */\n"
    "      fpstate = (unsigned)_ReadStatusReg(ARM64_FPCR);")
sub("src/util/u_math.c",
    "#elif DETECT_CC_MSVC\n      _WriteStatusReg(ARM64_FPCR, fpstate);",
    "#elif DETECT_CC_MSVC && !defined(__clang__) /* clang-cl: no ARM64_FPCR */\n"
    "      _WriteStatusReg(ARM64_FPCR, fpstate);")

sub("src/util/os_mman.h",
    "#if DETECT_OS_POSIX\n#  include <sys/mman.h>\n#else\n#  error Unsupported OS\n#endif",
    "#if DETECT_OS_POSIX || DETECT_OS_WINDOWS\n"
    "/* Windows: sys/mman.h comes from include/win32-compat. */\n"
    "#  include <sys/mman.h>\n#else\n#  error Unsupported OS\n#endif")

sub("src/util/os_mman.h",
    "static inline int os_munmap(void *addr, size_t length)\n{\n"
    "   /* Copied from configure code generated by AC_SYS_LARGEFILE */",
    "#if DETECT_OS_WINDOWS\n"
    "static inline int os_munmap(void *addr, size_t length)\n{\n"
    "   return munmap(addr, length);\n}\n"
    "#else\n"
    "static inline int os_munmap(void *addr, size_t length)\n{\n"
    "   /* Copied from configure code generated by AC_SYS_LARGEFILE */")

sub("src/util/os_mman.h",
    "   return munmap(addr, length);\n}\n#endif\n\n\n#ifdef __cplusplus",
    "   return munmap(addr, length);\n}\n#endif\n#endif\n\n\n#ifdef __cplusplus")

sub("src/panfrost/lib/kmod/pan_kmod.h",
    "#include <unistd.h>\n#include <xf86drm.h>",
    "#include <unistd.h>\n#include <sys/mman.h>\n#include <xf86drm.h>")

# --------------------------------------------------------------------------
# Panfrost MSVC ABI correctness: rebase of 0003/0011/0016 (and the parts of
# 0007 that still apply).  The manet 26.3 tree already has the public bool
# bitfields as unsigned, but its enum bitfields and packed instruction
# structures are unchanged.  Under the MSVC ABI an enum bitfield is signed,
# so a 3-bit enum bi_size reads BI_SIZE_64 (5) back as -3, and valhall's
# va_size/va_unit tables are misread; shader compilation then asserts and
# aborts inside vkCreateComputePipelines.  Enum bitfields are made unsigned,
# and the packed hardware structures are serialized by explicit helpers
# instead of trusting the compiler's bitfield layout.
# --------------------------------------------------------------------------

# 0003 + 0011: bifrost.h
bifrost_h = "src/panfrost/compiler/bifrost/bifrost.h"

sub(bifrost_h,
    "#include <stdint.h>\n#include <string.h>\n",
    "#include <stdint.h>\n#include <string.h>\n\n#include \"util/macros.h\"\n")

sub(bifrost_h,
    "   enum bifrost_ftz flush_to_zero : 2;",
    "   unsigned flush_to_zero : 2; /* enum bifrost_ftz */")
sub(bifrost_h,
    "   enum bifrost_exceptions float_exceptions : 2;",
    "   unsigned float_exceptions : 2; /* enum bifrost_exceptions */")
sub(bifrost_h,
    "   enum bifrost_flow flow_control : 3;",
    "   unsigned flow_control : 3; /* enum bifrost_flow */")

header_old = (
    "   enum bifrost_message_type message_type      : 5;\n"
    "   enum bifrost_message_type next_message_type : 5;\n"
    "} __attribute__((packed));")
header_new = (
    "   unsigned message_type      : 5; /* enum bifrost_message_type */\n"
    "   unsigned next_message_type : 5; /* enum bifrost_message_type */\n"
    "} PACKED;\n\n"
    "/* Packs struct bifrost_header in GCC's packed, LSB-first bitfield layout,\n"
    " * which is the hardware encoding. MSVC lays mixed-type bitfields out\n"
    " * differently, so the encoding must not depend on the struct's layout. */\n"
    "static inline uint64_t\n"
    "bifrost_header_pack(const struct bifrost_header *f)\n"
    "{\n"
    "   uint64_t v = 0;\n"
    "   v |= ((uint64_t)f->zero1 & 0x1full) << 0;\n"
    "   v |= ((uint64_t)f->flush_to_zero & 0x3ull) << 5;\n"
    "   v |= ((uint64_t)f->suppress_inf & 0x1ull) << 7;\n"
    "   v |= ((uint64_t)f->suppress_nan & 0x1ull) << 8;\n"
    "   v |= ((uint64_t)f->float_exceptions & 0x3ull) << 9;\n"
    "   v |= ((uint64_t)f->flow_control & 0x7ull) << 11;\n"
    "   v |= ((uint64_t)f->zero2 & 0x1ull) << 14;\n"
    "   v |= ((uint64_t)f->terminate_discarded_threads & 0x1ull) << 15;\n"
    "   v |= ((uint64_t)f->next_clause_prefetch & 0x1ull) << 16;\n"
    "   v |= ((uint64_t)f->staging_barrier & 0x1ull) << 17;\n"
    "   v |= ((uint64_t)f->staging_register & 0x3full) << 18;\n"
    "   v |= ((uint64_t)f->dependency_wait & 0xffull) << 24;\n"
    "   v |= ((uint64_t)f->dependency_slot & 0x7ull) << 32;\n"
    "   v |= ((uint64_t)f->message_type & 0x1full) << 35;\n"
    "   v |= ((uint64_t)f->next_message_type & 0x1full) << 40;\n"
    "   return v;\n"
    "}")
sub(bifrost_h, header_old, header_new)

sub(bifrost_h,
    "struct bifrost_fma_inst {\n"
    "   unsigned src0 : 3;\n"
    "   unsigned op   : 20;\n"
    "} __attribute__((packed));",
    "struct bifrost_fma_inst {\n"
    "   unsigned src0 : 3;\n"
    "   unsigned op   : 20;\n"
    "} PACKED;")
sub(bifrost_h,
    "struct bifrost_add_inst {\n"
    "   unsigned src0 : 3;\n"
    "   unsigned op   : 17;\n"
    "} __attribute__((packed));",
    "struct bifrost_add_inst {\n"
    "   unsigned src0 : 3;\n"
    "   unsigned op   : 17;\n"
    "} PACKED;")

regs_old = (
    "struct bifrost_regs {\n"
    "   unsigned fau_idx : 8;\n"
    "   unsigned reg3    : 6;\n"
    "   unsigned reg2    : 6;\n"
    "   unsigned reg0    : 5;\n"
    "   unsigned reg1    : 6;\n"
    "   unsigned ctrl    : 4;\n"
    "} __attribute__((packed));")
regs_new = (
    "struct bifrost_regs {\n"
    "   unsigned fau_idx : 8;\n"
    "   unsigned reg3    : 6;\n"
    "   unsigned reg2    : 6;\n"
    "   unsigned reg0    : 5;\n"
    "   unsigned reg1    : 6;\n"
    "   unsigned ctrl    : 4;\n"
    "} PACKED;\n\n"
    "/* Packs struct bifrost_regs in GCC's packed, LSB-first bitfield layout,\n"
    " * which is the hardware encoding. MSVC lays mixed-type bitfields out\n"
    " * differently, so the encoding must not depend on the struct's layout. */\n"
    "static inline uint64_t\n"
    "bifrost_regs_pack(const struct bifrost_regs *f)\n"
    "{\n"
    "   uint64_t v = 0;\n"
    "   v |= ((uint64_t)f->fau_idx & 0xffull) << 0;\n"
    "   v |= ((uint64_t)f->reg3 & 0x3full) << 8;\n"
    "   v |= ((uint64_t)f->reg2 & 0x3full) << 14;\n"
    "   v |= ((uint64_t)f->reg0 & 0x1full) << 20;\n"
    "   v |= ((uint64_t)f->reg1 & 0x3full) << 25;\n"
    "   v |= ((uint64_t)f->ctrl & 0xfull) << 31;\n"
    "   return v;\n"
    "}")
sub(bifrost_h, regs_old, regs_new)

fmt_old = (
    "struct bifrost_fmt_constant {\n"
    "   unsigned pos   : 4;\n"
    "   unsigned tag   : 4;\n"
    "   uint64_t imm_1 : 60;\n"
    "   uint64_t imm_2 : 60;\n"
    "} __attribute__((packed));")
fmt_new = (
    "struct bifrost_fmt_constant {\n"
    "   unsigned pos   : 4;\n"
    "   unsigned tag   : 4;\n"
    "   uint64_t imm_1 : 60;\n"
    "   uint64_t imm_2 : 60;\n"
    "} PACKED;\n\n"
    "/* Packs struct bifrost_fmt_constant (128 bits: pos 4, tag 4, imm_1 60,\n"
    " * imm_2 60) in GCC's packed bitfield layout; imm_1 straddles bit 64. */\n"
    "static inline void\n"
    "bifrost_fmt_constant_pack(const struct bifrost_fmt_constant *f,\n"
    "                          uint64_t out[2])\n"
    "{\n"
    "   uint64_t imm_1 = f->imm_1 & ((1ull << 60) - 1);\n"
    "   uint64_t imm_2 = f->imm_2 & ((1ull << 60) - 1);\n\n"
    "   out[0] = (f->pos & 0xfull) | ((f->tag & 0xfull) << 4) |\n"
    "            (imm_1 << 8);\n"
    "   out[1] = (imm_1 >> 56) | (imm_2 << 4);\n"
    "}")
sub(bifrost_h, fmt_old, fmt_new)

sub(bifrost_h,
    "         enum bifrost_tex_op op         : 3;",
    "         unsigned op         : 3; /* enum bifrost_tex_op */")
sub(bifrost_h,
    "         enum bifrost_texture_format_full format : 4;",
    "         unsigned format : 4; /* enum bifrost_texture_format_full */")

tex_tail_old = (
    "         /* Write mask for the result */\n"
    "         unsigned mask : 4;\n"
    "      };\n\n"
    "      uint32_t packed;\n"
    "   };\n"
    "} __attribute__((packed));\n\n"
    "struct bifrost_dual_texture_operation {")
tex_tail_new = (
    "         /* Write mask for the result */\n"
    "         unsigned mask : 4;\n"
    "      };\n\n"
    "      uint32_t packed;\n"
    "   };\n"
    "} PACKED;\n\n"
    "/* Packs struct bifrost_texture_operation in GCC's packed, LSB-first\n"
    " * bitfield layout, which is the hardware encoding. MSVC lays mixed-type\n"
    " * bitfields out differently, so the encoding must not depend on the\n"
    " * struct's layout. */\n"
    "static inline uint32_t\n"
    "bifrost_texture_operation_pack(\n"
    "   const struct bifrost_texture_operation *f)\n"
    "{\n"
    "   uint64_t v = 0;\n"
    "   v |= ((uint64_t)f->sampler_index_or_mode & 0xfull) << 0;\n"
    "   v |= ((uint64_t)f->index & 0x7full) << 4;\n"
    "   v |= ((uint64_t)f->immediate_indices & 0x1ull) << 11;\n"
    "   v |= ((uint64_t)f->op & 0x7ull) << 12;\n"
    "   v |= ((uint64_t)f->offset_or_bias_disable & 0x1ull) << 15;\n"
    "   v |= ((uint64_t)f->shadow_or_clamp_disable & 0x1ull) << 16;\n"
    "   v |= ((uint64_t)f->array & 0x1ull) << 17;\n"
    "   v |= ((uint64_t)f->dimension & 0x3ull) << 18;\n"
    "   v |= ((uint64_t)f->lod_or_fetch & 0x7ull) << 20;\n"
    "   v |= ((uint64_t)f->zero & 0x1ull) << 23;\n"
    "   v |= ((uint64_t)f->format & 0xfull) << 24;\n"
    "   v |= ((uint64_t)f->mask & 0xfull) << 28;\n"
    "   return (uint32_t)v;\n"
    "}\n\n"
    "struct bifrost_dual_texture_operation {")
sub(bifrost_h, tex_tail_old, tex_tail_new)

dual_old = (
    "   /* Format/mask for each texture */\n"
    "   enum bifrost_texture_format secondary_format : 3;\n"
    "   unsigned secondary_mask                      : 4;\n\n"
    "   enum bifrost_texture_format primary_format : 3;\n"
    "   unsigned primary_mask                      : 4;\n"
    "} __attribute__((packed));\n\n"
    "static inline uint32_t\n"
    "bi_dual_tex_as_u32(struct bifrost_dual_texture_operation desc)\n"
    "{\n"
    "   uint32_t desc_u;\n"
    "   memcpy(&desc_u, &desc, sizeof(desc));\n\n"
    "   return desc_u;\n"
    "}")
dual_new = (
    "   /* Format/mask for each texture */\n"
    "   unsigned secondary_format : 3; /* enum bifrost_texture_format */\n"
    "   unsigned secondary_mask                      : 4;\n\n"
    "   unsigned primary_format : 3; /* enum bifrost_texture_format */\n"
    "   unsigned primary_mask                      : 4;\n"
    "} PACKED;\n\n"
    "/* Packs struct bifrost_dual_texture_operation in GCC's packed, LSB-first\n"
    " * bitfield layout, which is the hardware encoding. */\n"
    "static inline uint32_t\n"
    "bifrost_dual_texture_operation_pack(\n"
    "   const struct bifrost_dual_texture_operation *f)\n"
    "{\n"
    "   uint64_t v = 0;\n"
    "   v |= ((uint64_t)f->primary_sampler_index & 0x3ull) << 0;\n"
    "   v |= ((uint64_t)f->mode & 0x3ull) << 2;\n"
    "   v |= ((uint64_t)f->primary_texture_index & 0x3ull) << 4;\n"
    "   v |= ((uint64_t)f->secondary_sampler_index & 0x3ull) << 6;\n"
    "   v |= ((uint64_t)f->secondary_texture_index & 0x3ull) << 8;\n"
    "   v |= ((uint64_t)f->reserved & 0x1ull) << 10;\n"
    "   v |= ((uint64_t)f->index_mode_zero & 0x1ull) << 11;\n"
    "   v |= ((uint64_t)f->secondary_register & 0x3full) << 12;\n"
    "   v |= ((uint64_t)f->secondary_format & 0x7ull) << 18;\n"
    "   v |= ((uint64_t)f->secondary_mask & 0xfull) << 21;\n"
    "   v |= ((uint64_t)f->primary_format & 0x7ull) << 25;\n"
    "   v |= ((uint64_t)f->primary_mask & 0xfull) << 28;\n"
    "   return (uint32_t)v;\n"
    "}\n\n"
    "static inline uint32_t\n"
    "bi_dual_tex_as_u32(struct bifrost_dual_texture_operation desc)\n"
    "{\n"
    "   return bifrost_dual_texture_operation_pack(&desc);\n"
    "}")
sub(bifrost_h, dual_old, dual_new)

sub(bifrost_h,
    "struct bifrost_pixel_indices {\n"
    "   unsigned sample : 8;\n"
    "   unsigned rt     : 8;\n"
    "   unsigned x      : 8;\n"
    "   unsigned y      : 8;\n"
    "} __attribute__((packed));",
    "struct bifrost_pixel_indices {\n"
    "   unsigned sample : 8;\n"
    "   unsigned rt     : 8;\n"
    "   unsigned x      : 8;\n"
    "   unsigned y      : 8;\n"
    "} PACKED;")

# 0003: use the explicit packers instead of copying the compiler's layout.
bi_pack_c = "src/panfrost/compiler/bifrost/bifrost/bi_pack.c"
sub(bi_pack_c,
    "   uint64_t u = 0;\n"
    "   memcpy(&u, &header, sizeof(header));\n"
    "   return u;",
    "   return bifrost_header_pack(&header);")
sub(bi_pack_c,
    "   memcpy(&packed, &s, sizeof(s));\n"
    "   return packed;",
    "   packed = bifrost_regs_pack(&s);\n"
    "   return packed;")
sub(bi_pack_c,
    "   util_dynarray_append(emission, quad);",
    "   uint64_t words[2];\n"
    "   bifrost_fmt_constant_pack(&quad, words);\n"
    "   util_dynarray_append(emission, words[0]);\n"
    "   util_dynarray_append(emission, words[1]);")

# 0003: texture descriptors are packed explicitly, not through .packed.
sub("src/panfrost/compiler/pan_nir_lower_tex.c",
    "nir_imm_int(b, desc.packed)",
    "nir_imm_int(b, bifrost_texture_operation_pack(&desc))",
    count=3)

# 0003/0007: statement expressions are a GCC extension; MSVC has none.
pan_nir_h = "src/panfrost/compiler/pan_nir.h"
sub(pan_nir_h,
    "#define PAN_AS_U32(x) ({\\\n"
    "   static_assert(sizeof(x) == 4, \"x must be 4 bytes\"); \\\n"
    "   uint32_t _u; \\\n"
    "   memcpy(&_u, &(x), 4); \\\n"
    "   _u; \\\n"
    "})",
    "/* Not a statement expression: MSVC has none. */\n"
    "static inline uint32_t\n"
    "pan_as_u32(const void *p, size_t size)\n"
    "{\n"
    "   uint32_t u;\n"
    "   assert(size == 4);\n"
    "   memcpy(&u, p, 4);\n"
    "   return u;\n"
    "}\n"
    "#define PAN_AS_U32(x) pan_as_u32(&(x), sizeof(x))")

# 0011: the Valhall source/opcode tables must read their enums unsigned.
valhall_h = "src/panfrost/compiler/bifrost/valhall/valhall.h"
sub(valhall_h,
    "   enum va_size size : 2;\n"
    "} __attribute__((packed));",
    "   unsigned size : 2; /* enum va_size */\n"
    "} PACKED;")
sub(valhall_h,
    "   enum va_unit unit         : 3;",
    "   unsigned unit : 3; /* enum va_unit */")

# 0011: the opcode metadata table is generated from this template.
sub("src/panfrost/compiler/bifrost/bi_opcodes.h.py",
    "        enum bifrost_message_type message : 4;\n"
    "        enum bi_size size : 3;\n"
    "        enum bi_sr_count sr_count : 3;",
    "        unsigned message : 4; /* enum bifrost_message_type */\n"
    "        unsigned size : 3; /* enum bi_size */\n"
    "        unsigned sr_count : 3; /* enum bi_sr_count */")

# 0011 + 0016: enum bitfields in the Gallium preload keys.  Not used by the
# v15 PanVK path, but the same MSVC ABI rule applies when D3D10 builds it.
pan_fb = "src/gallium/drivers/panfrost/pan_fb_preload.c"
sub(pan_fb,
    "   gl_frag_result loc              : 4;\n"
    "   nir_alu_type type               : 8;\n"
    "   enum mali_texture_dimension dim : 3;",
    "   unsigned loc                    : 4; /* gl_frag_result */\n"
    "   unsigned type                   : 8; /* nir_alu_type */\n"
    "   unsigned dim : 3; /* enum mali_texture_dimension */")
sub(pan_fb,
    "      nir_alu_type type               : 8;\n"
    "      unsigned samples                : 5;\n"
    "      enum mali_texture_dimension dim : 3;",
    "      unsigned type                   : 8; /* nir_alu_type */\n"
    "      unsigned samples                : 5;\n"
    "      unsigned dim : 3; /* enum mali_texture_dimension */")

# 0011: blend/equation keys (Gallium panfrost; kept consistent with 0003).
sub("src/panfrost/lib/pan_blend.h",
    "   enum pipe_blend_func rgb_func          : 3;\n"
    "   enum pipe_blendfactor rgb_src_factor   : 5;\n"
    "   enum pipe_blendfactor rgb_dst_factor   : 5;\n"
    "   enum pipe_blend_func alpha_func        : 3;\n"
    "   enum pipe_blendfactor alpha_src_factor : 5;\n"
    "   enum pipe_blendfactor alpha_dst_factor : 5;",
    "   unsigned rgb_func          : 3; /* enum pipe_blend_func */\n"
    "   unsigned rgb_src_factor   : 5; /* enum pipe_blendfactor */\n"
    "   unsigned rgb_dst_factor   : 5; /* enum pipe_blendfactor */\n"
    "   unsigned alpha_func        : 3; /* enum pipe_blend_func */\n"
    "   unsigned alpha_src_factor : 5; /* enum pipe_blendfactor */\n"
    "   unsigned alpha_dst_factor : 5; /* enum pipe_blendfactor */")

# 0011: Midgard is not built for the v15 Windows target, but the ABI rule is
# the same and the source is shared with the other Panfrost builds.
midgard_h = "src/panfrost/compiler/midgard/midgard.h"
sub(midgard_h,
    "   enum midgard_call_mode call_mode : 2;",
    "   unsigned call_mode : 2; /* enum midgard_call_mode */",
    count=2)
sub(midgard_h,
    "   enum mali_texture_op op             : 4;",
    "   unsigned op             : 4; /* enum mali_texture_op */")
sub(midgard_h,
    "   enum midgard_partial_execution exec : 2;",
    "   unsigned exec : 2; /* enum midgard_partial_execution */")
sub(midgard_h,
    "   enum mali_sampler_type sampler_type : 2;",
    "   unsigned sampler_type : 2; /* enum mali_sampler_type */")

# 0007: bi_index is hashed as 64 bits; build the key by fields so it does not
# depend on how MSVC packs the bitfield runs.
# 0007's bi_dump_shader PATH_MAX hunk is not applicable to manet 26.3: the
# dump helper moved to bifrost_nir.c and uses asprintf, so there is no
# PATH_MAX-sized stack buffer to fix.
sub("src/panfrost/compiler/bifrost/bifrost_compile.c",
    "   static_assert(sizeof(idx) <= sizeof(uint64_t), \"too much padding\");\n\n"
    "   uint64_t key = 0;\n"
    "   memcpy(&key, &idx, sizeof(idx));\n"
    "   return key;",
    "   /* Built field by field rather than by copying the struct: under the\n"
    "    * MSVC ABI each bool bitfield run takes its own storage unit, so a\n"
    "    * copy of the first 8 bytes could drop fields. */\n"
    "   uint64_t key = idx.value;\n"
    "   key |= (uint64_t)idx.abs << 32;\n"
    "   key |= (uint64_t)idx.neg << 33;\n"
    "   key |= (uint64_t)idx.discard << 34;\n"
    "   key |= (uint64_t)(idx.swizzle & 0x1f) << 35;\n"
    "   key |= (uint64_t)(idx.offset & 0x7) << 40;\n"
    "   key |= (uint64_t)(idx.type & 0x7) << 43;\n"
    "   key |= (uint64_t)idx.kill_ssa << 46;\n"
    "   key |= (uint64_t)idx.memory << 47;\n"
    "   return key;")

# 0003: sample tables are hardware-packed.
sub("src/panfrost/lib/pan_samples.c",
    "#include \"pan_samples.h\"\n",
    "#include \"pan_samples.h\"\n#include \"util/macros.h\"\n")
sub("src/panfrost/lib/pan_samples.c",
    "} __attribute__((packed));",
    "} PACKED;",
    count=2)

# 0003: mem->addr is void *, so do the byte arithmetic explicitly.
sub("src/panfrost/genxml/decode.h",
    "   return mem->addr + gpu_va - mem->gpu_va;",
    "   return (uint8_t *)mem->addr + (gpu_va - mem->gpu_va);")

# --------------------------------------------------------------------------
# Properties that manet 26.3 already provides.  Assert them so a future
# branch update cannot silently drop the MSVC fix these patches encode.
# (0004 bool bitfields and 0016/0001 location/section bitfields are upstream.)
# --------------------------------------------------------------------------
require("src/panfrost/compiler/bifrost/compiler.h",
        "   unsigned swizzle : 5;\n"
        "   uint32_t offset         : 3;\n"
        "   unsigned type : 3;",
        "bi_index enum bitfields must stay unsigned")
require("src/panfrost/compiler/pan_compiler.h",
        "   unsigned location : 7;",
        "pan_varying_slot location must stay unsigned")
require("src/panfrost/compiler/pan_compiler.h",
        "   unsigned section : 2;",
        "pan_varying_slot section must stay unsigned")
require("src/panfrost/compiler/pan_compiler.h",
        "   uint8_t known;",
        "pan_varying_layout must not use an enum bitfield (0006)")
require(pan_nir_h,
        "struct pan_bi_tex_flags {\n"
        "   unsigned skip : 1;\n"
        "   unsigned explicit_lod : 1;",
        "0004 bool bitfields must stay unsigned")
require(pan_nir_h,
        "struct pan_va_tex_flags {\n"
        "   unsigned skip : 1;",
        "0004 bool bitfields must stay unsigned")

# --------------------------------------------------------------------------
# 0025 + 0055: route assert() through a file logger when the build passes
# -D_wassert=mali_wassert.  The UCRT version raises a message box (or, in a
# windowless process, aborts); the Mesa assert text is what the shader
# compiler diagnostics need.
# --------------------------------------------------------------------------
create("src/util/mali_wassert.c", r'''/*
 * Assertions, without the message box. Windows only.
 *
 * The Windows build passes -D_wassert=mali_wassert, so every assert()
 * calls this instead of the C runtime.  This writes the assertion to
 * C:\mali\log\<exe>-<pid>-assert.txt (when that directory exists), to
 * stderr and to the debugger, and returns, which is what Ignore does.
 */
#ifdef _WIN32

#include <windows.h>
#include <stdio.h>

static void __cdecl
mali_wassert_impl(const wchar_t *message, const wchar_t *file, unsigned line)
{
   static volatile LONG count = 0;
   static HANDLE log = NULL;
   char buf[1024];
   int len;
   DWORD done;

   if (InterlockedIncrement(&count) > 2000)
      return;
   len = snprintf(buf, sizeof buf, "%10lu %5lu ASSERT %ls:%u: %ls\n",
                  (unsigned long)GetTickCount(), (unsigned long)GetCurrentThreadId(),
                  file, line, message);
   if (len <= 0)
      return;
   if (len >= (int)sizeof buf)
      len = (int)sizeof buf - 1;
   OutputDebugStringA(buf);
   fputs(buf, stderr);

   if (log == NULL) {
      HANDLE h = INVALID_HANDLE_VALUE;
      if (GetFileAttributesA("C:\\mali\\log") != INVALID_FILE_ATTRIBUTES) {
         char exe[MAX_PATH], path[MAX_PATH];
         const char *base = exe;
         DWORD n = GetModuleFileNameA(NULL, exe, sizeof exe);
         exe[n < sizeof exe ? n : sizeof exe - 1] = 0;
         for (const char *c = exe; *c; c++)
            if (*c == '\\' || *c == '/')
               base = c + 1;
         snprintf(path, sizeof path, "C:\\mali\\log\\%s-%lu-assert.txt", base,
                  (unsigned long)GetCurrentProcessId());
         h = CreateFileA(path, FILE_APPEND_DATA,
                         FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                         NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
      }
      if (InterlockedCompareExchangePointer((PVOID volatile *)&log, h, NULL) != NULL &&
          h != INVALID_HANDLE_VALUE)
         CloseHandle(h);
   }
   if (log != INVALID_HANDLE_VALUE)
      WriteFile(log, buf, (DWORD)len, &done, NULL);
}

/* What "__declspec(dllimport) mali_wassert" resolves to. */
void (__cdecl *__imp_mali_wassert)(const wchar_t *, const wchar_t *, unsigned) = mali_wassert_impl;

#ifndef _DLL
/* With the static C runtime (/MT) assert.h does not declare _wassert
 * dllimport: the calls name the function itself, so define it. */
void __cdecl
mali_wassert(const wchar_t *message, const wchar_t *file, unsigned line)
{
   mali_wassert_impl(message, file, line);
}
#endif

#endif
''')

sub("src/util/meson.build",
    "  'u_debug.c',\n"
    "  'u_debug.h',",
    "  'u_debug.c',\n"
    "  'mali_wassert.c',\n"
    "  'u_debug.h',")

# --------------------------------------------------------------------------
# kmod build: use the vdrm transport instead of the Linux virtgpu ioctls.
# --------------------------------------------------------------------------
sub("src/panfrost/lib/kmod/meson.build",
    "  libpankmod_lib_files += files('kbase_kmod.c', 'mali_kbase_virtio.c')",
    "  libpankmod_lib_files += files('kbase_kmod.c', 'mali_kbase_vdrm_win.c',\n"
    "                                'win32_stubs.c', 'vdrm/vdrm.c',\n"
    "                                'vdrm/vdrm_wddm.c')")

sub("src/panfrost/lib/kmod/meson.build",
    "  include_directories : [inc_include, inc_src, inc_panfrost],",
    "  include_directories : [inc_include, inc_src, inc_panfrost,\n"
    "                         include_directories('vdrm')],")

sub("src/panfrost/lib/kmod/meson.build",
    "  dependencies: [dep_libdrm, idep_mesautil, idep_pan_packers, libpanfrost_model_dep],",
    "  dependencies: [idep_mesautil, idep_pan_packers, libpanfrost_model_dep],")

sub("src/panfrost/lib/kmod/meson.build",
    "  dependencies: [dep_libdrm],",
    "  dependencies: [],")

# --------------------------------------------------------------------------
# PanVK: no libdrm on Windows; link the pankmod static library.
# --------------------------------------------------------------------------
sub("src/panfrost/vulkan/meson.build", "      dep_libdrm,\n", "", count=10)
sub("src/panfrost/vulkan/meson.build", "    dep_libdrm,\n", "", count=10)
sub("src/panfrost/vulkan/meson.build",
    "  link_with : [\n    libpanfrost_shared,",
    "  link_with : [\n    libpankmod_lib,\n    libpanfrost_shared,")

# --------------------------------------------------------------------------
# Instance enumeration: skip DRM on Windows, use the WDDM kbase device.
# --------------------------------------------------------------------------
wrap("src/panvk/instance.c" if (root / "src/panvk/instance.c").exists()
     else "src/panfrost/vulkan/panvk_instance.c",
     "static VkResult\npanvk_physical_device_try_create",
     "static VkResult\npanvk_enumerate_physical_devices",
     "#ifndef _WIN32\n")

sub("src/panfrost/vulkan/panvk_instance.c",
    "   /* Enumerate DRM render nodes (panfrost / panthor). */",
    "#ifndef _WIN32\n   /* Enumerate DRM render nodes (panfrost / panthor). */")

sub("src/panfrost/vulkan/panvk_instance.c",
    "#if defined(HAVE_PAN_KMOD_KBASE)\n   /* Enumerate kbase (Mali) non-DRM nodes. */",
    "#endif /* !_WIN32 */\n\n"
    "#if defined(HAVE_PAN_KMOD_KBASE)\n"
    "#ifdef _WIN32\n"
    "   /* Windows: one virtio WDDM kbase device; vdrm owns the connection. */\n"
    "   fprintf(stderr, \"[panvk-win] enumerate: Windows kbase branch, HAVE_PAN_KMOD_KBASE=1\\n\");\n"
    "   fflush(stderr);\n"
    "   struct panvk_physical_device *device =\n"
    "      vk_zalloc(&instance->vk.alloc, sizeof(*device), 8,\n"
    "                VK_SYSTEM_ALLOCATION_SCOPE_INSTANCE);\n"
    "   if (!device)\n"
    "      return panvk_error(instance, VK_ERROR_OUT_OF_HOST_MEMORY);\n"
    "   VkResult result =\n"
    "      panvk_physical_device_init_kbase(device, instance, \"wddm\");\n"
    "   fprintf(stderr, \"[panvk-win] init_kbase(\\\"wddm\\\") -> %d (%s)\\n\",\n"
    "           (int)result, result == VK_SUCCESS ? \"VK_SUCCESS\" : \"error\");\n"
    "   fflush(stderr);\n"
    "   if (result != VK_SUCCESS) {\n"
    "      vk_free(&instance->vk.alloc, device);\n"
    "      if (result == VK_ERROR_INCOMPATIBLE_DRIVER)\n"
    "         return VK_SUCCESS; /* no virtio WDDM adapter: zero devices */\n"
    "      return result;\n"
    "   }\n"
    "   list_addtail(&device->vk.link, &vk_instance->physical_devices.list);\n"
    "#else\n"
    "   /* Enumerate kbase (Mali) non-DRM nodes. */")

sub("src/panfrost/vulkan/panvk_instance.c",
    "      list_addtail(&device->vk.link, &vk_instance->physical_devices.list);\n"
    "   }\n#endif /* HAVE_PAN_KMOD_KBASE */\n\n   return VK_SUCCESS;\n}",
    "      list_addtail(&device->vk.link, &vk_instance->physical_devices.list);\n"
    "   }\n#endif /* !_WIN32 */\n#endif /* HAVE_PAN_KMOD_KBASE */\n\n"
    "   return VK_SUCCESS;\n}")

# --------------------------------------------------------------------------
# Physical device: open the WDDM transport without a /dev/mali node.
# --------------------------------------------------------------------------
sub("src/panfrost/vulkan/panvk_physical_device.c",
    "#include <errno.h>",
    "#include <errno.h>\n#ifdef _WIN32\n#include <io.h>\n#include <fcntl.h>\n"
    "#include <stdio.h>\n"
    "#include <pthread.h>\n#define strtok_r strtok_s\n#endif")

sub("src/panfrost/vulkan/panvk_physical_device.c",
    "   fd = open(path, O_RDWR | O_CLOEXEC);\n"
    "   if (fd < 0) {\n"
    "      return panvk_errorf(instance, VK_ERROR_INCOMPATIBLE_DRIVER,\n"
    "                          \"failed to open kbase device %s\", path);",
    "#ifdef _WIN32\n"
    "   /* vdrm owns the KMD connection; the CRT fd is only a kbv key. */\n"
    "   fprintf(stderr, \"[panvk-win] create_kmod_dev_kbase path=%s\\n\", path);\n"
    "   fd = _open(\"NUL\", _O_RDWR);\n"
    "   fprintf(stderr, \"[panvk-win] _open(NUL) fd=%d errno=%d\\n\", fd, errno);\n"
    "   fflush(stderr);\n"
    "#else\n"
    "   fd = open(path, O_RDWR | O_CLOEXEC);\n"
    "#endif\n"
    "   if (fd < 0) {\n"
    "      return panvk_errorf(instance, VK_ERROR_INCOMPATIBLE_DRIVER,\n"
    "                          \"failed to open kbase device %s\", path);")

sub("src/panfrost/vulkan/panvk_physical_device.c",
    "   device->kmod.dev = pan_kmod_dev_create_with_driver(fd, flags, \"kbase\", NULL,\n"
    "                                                      &instance->kmod.allocator);\n\n"
    "   if (!device->kmod.dev) {",
    "   fprintf(stderr, \"[panvk-win] calling pan_kmod_dev_create_with_driver(\\\"kbase\\\") fd=%d flags=0x%x\\n\",\n"
    "           fd, flags);\n"
    "   fflush(stderr);\n"
    "   device->kmod.dev = pan_kmod_dev_create_with_driver(fd, flags, \"kbase\", NULL,\n"
    "                                                      &instance->kmod.allocator);\n"
    "   fprintf(stderr, \"[panvk-win] pan_kmod_dev_create_with_driver -> %p\\n\",\n"
    "           (void *)device->kmod.dev);\n"
    "   fflush(stderr);\n\n"
    "   if (!device->kmod.dev) {")

sub("src/panfrost/vulkan/panvk_physical_device.c",
    "   configure_kbase_dvfs(path);",
    "#ifndef _WIN32\n   configure_kbase_dvfs(path);\n#endif")

sub("src/panfrost/vulkan/panvk_physical_device.c",
    "   case 6:\n   case 7:\n   case 14:\n   case 15:\n"
    "      if (!os_get_option(\"PAN_I_WANT_A_BROKEN_VULKAN_DRIVER\")) {",
    "   case 6:\n   case 7:\n   case 14:\n   case 15:\n"
    "#ifdef _WIN32\n"
    "      /* G2-Ultra (arch 15) is the validated native-context target. */\n"
    "      break;\n"
    "#endif\n"
    "      if (!os_get_option(\"PAN_I_WANT_A_BROKEN_VULKAN_DRIVER\")) {")

# The DRM-only init path is not built on Windows.  The kbase init after it is.
wrap("src/panfrost/vulkan/panvk_physical_device.c",
     "static VkResult\ncreate_kmod_dev(",
     "#if defined(HAVE_PAN_KMOD_KBASE)",
     "#ifndef _WIN32\n")

wrap("src/panfrost/vulkan/panvk_physical_device.c",
     "static VkResult\nget_drm_device_ids",
     "static void\ninit_shader_caches",
     "#ifndef _WIN32\n")

wrap("src/panfrost/vulkan/panvk_physical_device.c",
     "static VkResult\nget_device_sync_types(",
     "#if defined(HAVE_PAN_KMOD_KBASE)",
     "#ifndef _WIN32\n")

wrap("src/panfrost/vulkan/panvk_physical_device.c",
     "VkResult\npanvk_physical_device_init(",
     "#if defined(HAVE_PAN_KMOD_KBASE)",
     "#ifndef _WIN32\n")

# Logical device: it re-opens the kbase node for a fresh context; on Windows
# use the NUL fd key and let vdrm own the connection.
sub("src/panfrost/vulkan/panvk_vX_device.c",
    "#ifdef HAVE_PAN_KMOD_KBASE\n#include <fcntl.h>\n#endif",
    "#ifdef HAVE_PAN_KMOD_KBASE\n#include <fcntl.h>\n"
    "#ifdef _WIN32\n#include <io.h>\n#include <stdio.h>\n#endif\n#endif")

sub("src/panfrost/vulkan/panvk_vX_device.c",
    "      int kbase_fd =\n"
    "         open(physical_device->kbase_node_path, O_RDWR | O_CLOEXEC);",
    "#ifdef _WIN32\n"
    "      int kbase_fd = _open(\"NUL\", _O_RDWR);\n"
    "#else\n"
    "      int kbase_fd =\n"
    "         open(physical_device->kbase_node_path, O_RDWR | O_CLOEXEC);\n"
    "#endif\n"
    "      fprintf(stderr, \"[panvk-win] create_device kbase_fd=%d errno=%d path=%s\\n\",\n"
    "              kbase_fd, errno, physical_device->kbase_node_path);\n"
    "      fflush(stderr);")

sub("src/panfrost/vulkan/panvk_vX_device.c",
    "         if (!device->kmod.dev)\n            close(kbase_fd);",
    "         fprintf(stderr, \"[panvk-win] create_device kmod.dev=%p errno=%d\\n\",\n"
    "                 (void *)device->kmod.dev, errno);\n"
    "         fflush(stderr);\n"
    "         if (!device->kmod.dev)\n            close(kbase_fd);")

sub("src/panfrost/vulkan/panvk_vX_device.c",
    "   if (!device->kmod.dev) {\n"
    "      result = panvk_errorf(instance, VK_ERROR_OUT_OF_HOST_MEMORY,\n"
    "                            \"cannot create device\");",
    "   fprintf(stderr, \"[panvk-win] create_device final kmod.dev=%p errno=%d\\n\",\n"
    "           (void *)device->kmod.dev, errno);\n"
    "   fflush(stderr);\n"
    "   if (!device->kmod.dev) {\n"
    "      result = panvk_errorf(instance, VK_ERROR_OUT_OF_HOST_MEMORY,\n"
    "                            \"cannot create device\");")

sub("src/panfrost/vulkan/panvk_vX_device.c",
    "   device->kmod.vm =\n"
    "      pan_kmod_vm_create(device->kmod.dev, vm_flags,\n"
    "                         user_va_start, user_va_end - user_va_start);",
    "   device->kmod.vm =\n"
    "      pan_kmod_vm_create(device->kmod.dev, vm_flags,\n"
    "                         user_va_start, user_va_end - user_va_start);\n"
    "   fprintf(stderr, \"[panvk-win] pan_kmod_vm_create -> %p errno=%d\\n\",\n"
    "           (void *)device->kmod.vm, errno);\n"
    "   fflush(stderr);")

sub("src/panfrost/vulkan/panvk_vX_device.c",
    "   result = panvk_per_arch(init_tiler_oom)(device);\n"
    "   if (result != VK_SUCCESS)",
    "   result = panvk_per_arch(init_tiler_oom)(device);\n"
    "   fprintf(stderr, \"[panvk-win] init_tiler_oom -> %d\\n\", (int)result);\n"
    "   fflush(stderr);\n"
    "   if (result != VK_SUCCESS)")

sub("src/panfrost/vulkan/panvk_vX_device.c",
    "panvk_per_arch(create_device)(struct panvk_physical_device *physical_device,\n"
    "                              const VkDeviceCreateInfo *pCreateInfo,\n"
    "                              const VkAllocationCallbacks *pAllocator,\n"
    "                              VkDevice *pDevice)\n"
    "{\n"
    "   struct panvk_instance *instance =\n"
    "      to_panvk_instance(physical_device->vk.instance);\n"
    "   VkResult result;",
    "panvk_per_arch(create_device)(struct panvk_physical_device *physical_device,\n"
    "                              const VkDeviceCreateInfo *pCreateInfo,\n"
    "                              const VkAllocationCallbacks *pAllocator,\n"
    "                              VkDevice *pDevice)\n"
    "{\n"
    "   struct panvk_instance *instance =\n"
    "      to_panvk_instance(physical_device->vk.instance);\n"
    "   VkResult result;\n"
    "   fprintf(stderr, \"[panvk-win] create_device: enter\\n\");\n"
    "   fflush(stderr);")

sub("src/panfrost/vulkan/panvk_priv_bo.c",
    "#include \"kmod/pan_kmod.h\"",
    "#include \"kmod/pan_kmod.h\"\n#ifdef _WIN32\n#include <stdio.h>\n#endif")
sub("src/panfrost/vulkan/panvk_priv_bo.c",
    "   struct pan_kmod_bo *bo =\n"
    "      pan_kmod_bo_alloc(dev->kmod.dev, dev->kmod.vm, size, flags);\n"
    "   if (!bo) {",
    "   struct pan_kmod_bo *bo =\n"
    "      pan_kmod_bo_alloc(dev->kmod.dev, dev->kmod.vm, size, flags);\n"
    "   if (!bo) {\n"
    "      fprintf(stderr, \"[panvk-win] priv_bo_create size=%llu flags=0x%x -> NULL errno=%d\\n\",\n"
    "              (unsigned long long)size, flags, errno);\n"
    "      fflush(stderr);")

# --------------------------------------------------------------------------
# WSI: no DRM device on Windows; wsi_common still supplies the Win32/GDI
# surface.  Keep the default CPU path.
# --------------------------------------------------------------------------
wrap("src/panfrost/vulkan/panvk_wsi.c",
     "static bool\npanvk_can_present_on_device",
     "VkResult\npanvk_wsi_init",
     "#ifndef _WIN32\n")

sub("src/panfrost/vulkan/panvk_wsi.c",
    "   physical_device->wsi_device.can_present_on_device =\n"
    "      panvk_can_present_on_device;",
    "#ifndef _WIN32\n"
    "   physical_device->wsi_device.can_present_on_device =\n"
    "      panvk_can_present_on_device;\n"
    "#else\n"
    "   physical_device->wsi_device.can_present_on_device = NULL;\n"
    "#endif")

# --------------------------------------------------------------------------
# kbase_kmod: the tracking page is anonymous memory, not an mmap.
# --------------------------------------------------------------------------
sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "   void *tracking_page = virtio ? mmap(NULL, 4096, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) :\n"
    "      mmap(NULL, 4096, PROT_NONE, MAP_SHARED, fd, BASE_MEM_MAP_TRACKING_HANDLE);\n"
    "   if (tracking_page == MAP_FAILED) {",
    "#ifdef _WIN32\n"
    "   void *tracking_page = virtio ? calloc(1, 4096) : MAP_FAILED;\n"
    "   if (!tracking_page) {\n"
    "#else\n"
    "   void *tracking_page = virtio ? mmap(NULL, 4096, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) :\n"
    "      mmap(NULL, 4096, PROT_NONE, MAP_SHARED, fd, BASE_MEM_MAP_TRACKING_HANDLE);\n"
    "   if (tracking_page == MAP_FAILED) {\n"
    "#endif")

sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "munmap(tracking_page, 4096)", "free(tracking_page)", count=10)

# --------------------------------------------------------------------------
# A Windows drmDevicePtr forward declaration for the DRM-only prototypes.
# --------------------------------------------------------------------------
sub("include/win32-compat/xf86drm.h",
    "#include <stdint.h>",
    "#include <stdint.h>\n\n#ifndef _WIN32_DRM_DEVICE_PTR\n"
    "#define _WIN32_DRM_DEVICE_PTR\ntypedef struct _drmDevice *drmDevicePtr;\n#endif")

sub("src/panfrost/vulkan/panvk_physical_device.h",
    "#include <stdint.h>\n#include <sys/types.h>",
    "#include <stdint.h>\n#include <sys/types.h>\n"
    "#ifdef _WIN32\n#ifndef _WIN32_DRM_DEVICE_PTR\n"
    "#define _WIN32_DRM_DEVICE_PTR\n"
    "typedef struct _drmDevice *drmDevicePtr;\n#endif\n#endif")

# kbase_kmod's dma-buf duplicate path uses POSIX fcntl; MSVC has _dup.
sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "#include <fcntl.h>",
    "#include <fcntl.h>\n#ifdef _WIN32\n#include <io.h>\n#endif")
sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "fcntl(fd, F_DUPFD_CLOEXEC, 3)", "_dup(fd)")
sub("src/panfrost/lib/kmod/kbase_kmod.c",
    "fcntl(kbase_bo->dmabuf_fd, F_DUPFD_CLOEXEC, 3)",
    "_dup(kbase_bo->dmabuf_fd)")

print(f"patch_mesa: {changes} edits applied, {len(misses)} anchors missing")
for m in misses:
    print("  MISS:", m)
sys.exit(0 if not misses else 2)
