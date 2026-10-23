#ifndef MMX6_COOP_HOST_LAB_H
#define MMX6_COOP_HOST_LAB_H
#include "mod_netplay.h"
#if defined(PSX_MOD_NETPLAY_HOST_CATALOG_API) && PSX_MOD_NETPLAY_HOST_CATALOG_API >= 2
int mmx6_coop_lab_host_profiles(const PSXModNetplayHostStartup *,PSXHostProfileCatalog *);
#endif
#endif
