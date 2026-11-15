#pragma once
#include <sys/ioctl.h>
#ifndef _IOC_WRITE
#define _IOC_WRITE 1U
#define _IOC_READ  2U
#endif
#ifndef _IOC_SIZE
#define _IOC_SIZE(nr) (((nr) >> 16) & 0x3fff)
#endif
