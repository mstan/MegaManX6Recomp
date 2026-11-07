#ifndef MMX6_COOP_HOST_LAB_H
#define MMX6_COOP_HOST_LAB_H
#include "mod_netplay.h"
#if defined(PSX_MOD_NETPLAY_HOST_CATALOG_API) && PSX_MOD_NETPLAY_HOST_CATALOG_API >= 2
#include "mmx6_coop_host_lab_contract.h"
#include "mmx6_coop_portable_cpu_host_lab_contract.h"
#include "mmx6_coop_release_host_profile.h"
#include <string.h>
int mmx6_coop_lab_host_profiles(const PSXModNetplayHostStartup *,PSXHostProfileCatalog *);
int mmx6_coop_release_host_profiles(const PSXModNetplayHostStartup *,PSXHostProfileCatalog *);
int mmx6_coop_host_profiles(const PSXModNetplayHostStartup *,PSXHostProfileCatalog *);
/* The agreed lab fixture accepts only the exact settled cell identities.
 * A portable CPU candidate never bypasses the SDK's actual-artifact gate. */
static inline int mmx6_coop_lab_selection_matches(const PSXHostSelection *selected){
    if(!selected)return 0;
#if defined(MMX6_ENABLE_LOOPBACK_HOST_LAB) && MMX6_ENABLE_LOOPBACK_HOST_LAB
    const uint8_t exact[32]=MMX6_HOST_LAB_QUALIFICATION_BYTES;
    if(!strcmp(selected->profile,MMX6_HOST_LAB_PROFILE)&&selected->revision==MMX6_HOST_LAB_REVISION&&
       selected->flags==PSX_HOST_PROFILE_DIRECT_LOOPBACK&&
       !memcmp(selected->qualification,exact,sizeof exact))return 1;
#if defined(MMX6_ENABLE_PORTABLE_CPU_HOST_LAB) && MMX6_ENABLE_PORTABLE_CPU_HOST_LAB
    const uint8_t portable[32]=MMX6_PORTABLE_CPU_HOST_LAB_QUALIFICATION_BYTES;
    if(!strcmp(selected->profile,MMX6_PORTABLE_CPU_HOST_LAB_PROFILE)&&
       selected->revision==MMX6_PORTABLE_CPU_HOST_LAB_REVISION&&
       selected->flags==(PSX_HOST_PROFILE_DIRECT_LOOPBACK|PSX_HOST_PROFILE_PORTABLE)&&
       !memcmp(selected->qualification,portable,sizeof portable))return 1;
#endif
#endif
    return 0;
}
#endif
#endif
