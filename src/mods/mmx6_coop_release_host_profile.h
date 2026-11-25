/* Normal-build policy identity, separate from the lab rules. Its SHA-256
 * identifies the exact policy text below. Native LAN qualification remains
 * required on the final same-executable normal pair before release. */
#ifndef MMX6_COOP_RELEASE_HOST_PROFILE_H
#define MMX6_COOP_RELEASE_HOST_PROFILE_H
#define MMX6_RELEASE_HOST_PROFILE "mmx6.win64.enhanced.release"
#define MMX6_RELEASE_HOST_REVISION 2u
#define MMX6_RELEASE_HOST_EXECUTION_ID "21cc31a9f256438d4117e938071b7e836f70aa6f60c3ed96f053db131100bcaf"
#define MMX6_RELEASE_HOST_POLICY "mmx6.win64.enhanced.release/v2;kernel=host-native-v1;abi=win64-mingw-clang22.1.8;execution=21cc31a9f256438d4117e938071b7e836f70aa6f60c3ed96f053db131100bcaf;cpu=x64-portable-known;fp=2;bios=OPENBIOS:c4daeb88;overlays=interpreted-sealed;manifest=sha256-v1;artifact=exact;seats=2;rollback=off;loading=on;renderer=retained-opengl;aspect=4:3;lab=off;debug=off;route=normal;native-lan-qualification=required"
#define MMX6_RELEASE_HOST_QUALIFICATION_BYTES {0x02,0x3b,0xeb,0x7a,0xbf,0xd0,0x99,0x88,0x07,0x77,0x9c,0x2f,0xac,0xf5,0x8e,0xb4,0xdf,0x03,0xf0,0x66,0x6b,0xda,0x67,0xf4,0x4a,0xc8,0xff,0xba,0x39,0xe3,0x94,0xc0}
#endif
