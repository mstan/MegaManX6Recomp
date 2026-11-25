/* Normal-build policy identity, separate from the lab rules. Its SHA-256
 * identifies the exact policy text below. Native LAN qualification remains
 * required on the final same-executable normal pair before release. */
#ifndef MMX6_COOP_RELEASE_HOST_PROFILE_H
#define MMX6_COOP_RELEASE_HOST_PROFILE_H
#define MMX6_RELEASE_HOST_PROFILE "mmx6.win64.enhanced.release"
#define MMX6_RELEASE_HOST_REVISION 2u
#define MMX6_RELEASE_HOST_EXECUTION_ID "e4f99a226032c59f67faca36bec53cfe102c9d5a495fbfcacc304d3193f03afe"
#define MMX6_RELEASE_HOST_POLICY "mmx6.win64.enhanced.release/v2;kernel=host-native-v1;abi=win64-mingw-clang22.1.8;execution=e4f99a226032c59f67faca36bec53cfe102c9d5a495fbfcacc304d3193f03afe;cpu=x64-portable-known;fp=2;bios=OPENBIOS:c4daeb88;overlays=interpreted-sealed;manifest=sha256-v1;artifact=exact;seats=2;rollback=off;loading=on;renderer=retained-opengl;aspect=4:3;lab=off;debug=off;route=normal;native-lan-qualification=required"
#define MMX6_RELEASE_HOST_QUALIFICATION_BYTES {0x3e,0x7d,0xbb,0x6a,0x08,0x13,0x4e,0xd0,0xeb,0x66,0xb9,0x54,0xf1,0x21,0x0c,0x1b,0xb2,0xf2,0x2e,0x6a,0x35,0x3d,0xaf,0x31,0xe9,0x49,0x2f,0x72,0x7c,0x31,0x55,0x19}
#endif
