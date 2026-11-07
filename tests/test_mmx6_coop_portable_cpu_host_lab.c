/* Reuse the real title callback fixture; no runtime CPU override. */
#define main legacy_host_lab_fixture_main
#include "test_mmx6_coop_host_lab.c"
#undef main
#if defined(PSX_MOD_NETPLAY_HOST_CATALOG_API) && PSX_MOD_NETPLAY_HOST_CATALOG_API >= 2
#ifndef MMX6_PORTABLE_CPU_HOST_LAB_EXPECT_OFFER
#error Explicit expected portable eligibility is required.
#endif
static void no_offer(PSXModNetplayHostStartup c){
    PSXHostProfileCatalog cat={(const PSXHostProfileRule *)(uintptr_t)1,9};
    CHECK(!mmx6_coop_lab_host_profiles(&c,&cat)&&!cat.rules&&!cat.count);
}
int main(void){
    PSXModNetplayHostStartup c=valid();c.cpu.features=0x3f;
    CHECK(!lab_context_eligible(&c,MMX6_HOST_LAB_EXECUTION_ID));
    CHECK(lab_portable_cpu_context_eligible(&c,MMX6_HOST_LAB_EXECUTION_ID));
    PSXHostProfileCatalog cat={0};
    CHECK(mmx6_coop_lab_host_profiles(&c,&cat)==MMX6_PORTABLE_CPU_HOST_LAB_EXPECT_OFFER);
    if(MMX6_PORTABLE_CPU_HOST_LAB_EXPECT_OFFER){
        CHECK(cat.count==1&&cat.rules);
        CHECK(!strcmp(cat.rules[0].profile,MMX6_PORTABLE_CPU_HOST_LAB_PROFILE));
        CHECK(cat.rules[0].revision==130&&cat.rules[0].implementation_count==1);
        CHECK(cat.rules[0].flags==(PSX_HOST_PROFILE_PORTABLE|PSX_HOST_PROFILE_DIRECT_LOOPBACK));
        CHECK(cat.rules[0].implementations[0].required_features==0);
        CHECK(cat.rules[0].implementations[0].backend==PSX_HOST_BACKEND_ENHANCED);
        PSXHostCapabilities peers[2];
        for(unsigned i=0;i<2;++i){
            CHECK(psx_host_caps_init(peers+i,&c.cpu,2,2,artifact));
            CHECK(psx_host_caps_offer(peers+i,cat.rules,2));
            CHECK(psx_host_caps_validate(peers+i,&cat));
        }
        uint8_t session[32]={2};PSXHostMatch match;
        psx_host_match_init(&match);
        CHECK(psx_host_match_select(&match,peers,2,&cat,session)==PSX_HOST_OK);
        CHECK(!strcmp(match.selected.profile,MMX6_PORTABLE_CPU_HOST_LAB_PROFILE));
        CHECK(mmx6_coop_lab_selection_matches(&match.selected));
        PSXHostSelection bad=match.selected;bad.qualification[0]^=1;
        CHECK(!mmx6_coop_lab_selection_matches(&bad));
        bad=match.selected;bad.revision=100;CHECK(!mmx6_coop_lab_selection_matches(&bad));
        bad=match.selected;bad.flags=PSX_HOST_PROFILE_PORTABLE;CHECK(!mmx6_coop_lab_selection_matches(&bad));
        /* PORTABLE never relaxes actual image identity. */
        peers[1].build[0]^=2;psx_host_match_init(&match);
        CHECK(psx_host_match_select(&match,peers,2,&cat,session)==PSX_HOST_BUILD_MISMATCH);
        c=valid();c.cpu.features=0;
        CHECK(mmx6_coop_lab_host_profiles(&c,&cat)&&cat.count==1);
        c=valid();CHECK(mmx6_coop_lab_host_profiles(&c,&cat)&&cat.count==2);
        CHECK(!strcmp(cat.rules[0].profile,MMX6_HOST_LAB_PROFILE)&&cat.rules[0].revision==129);
        CHECK(cat.rules[0].flags==PSX_HOST_PROFILE_DIRECT_LOOPBACK&&cat.rules[0].priority>cat.rules[1].priority);
        PSXHostSelection legacy={0};strcpy(legacy.profile,cat.rules[0].profile);
        legacy.revision=cat.rules[0].revision;legacy.flags=cat.rules[0].flags;
        memcpy(legacy.qualification,cat.rules[0].qualification,32);
        CHECK(mmx6_coop_lab_selection_matches(&legacy));
    }
    c=valid();c.cpu.features=0x3f;c.cpu.features_known=0;no_offer(c);
    c=valid();c.cpu.architecture=PSX_HOST_ARCH_ARM64;no_offer(c);
    c=valid();c.compiled_backends=PSX_HOST_BACKEND_REFERENCE;no_offer(c);
    c=valid();c.available_backends=0;no_offer(c);
    c=valid();c.fp_contract=1;no_offer(c);
    c=valid();c.interpreted_overlays_sealed=0;no_offer(c);
    c=valid();c.direct_loopback_scope=0;no_offer(c);
    c=valid();c.rollback=1;no_offer(c);
    c=valid();c.renderer=0;no_offer(c);
    c=valid();c.loading_enabled=0;no_offer(c);
    c=valid();c.builtin_bios_image_id="other";no_offer(c);
    c=valid();c.actual_executable_sha256=NULL;no_offer(c);
    c=valid();c.declared_build_manifest_sha256="bad";no_offer(c);
    c=valid();title.compatibility_id="other";no_offer(c);
    CHECK(!mmx6_coop_lab_selection_matches(NULL));
    puts("portable CPU candidate offer/strict artifact/fixture authority checks PASS; native qualification remains required");
    return 0;
}
#else
int main(void){puts("old SDK: portable CPU catalog unavailable");return 0;}
#endif
