/* SLUS-01395 original source guards for the explicit F101/F116 prerequisite.
 * EXE dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046;
 * BIN2 d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607.
 * No disc bytes are distributed. FNV guards supplement the parent's exact
 * original/build identity checks; they are not cryptographic identities. */
#ifndef MMX6_COOP_BEFORE_DOORS_DATA_H
#define MMX6_COOP_BEFORE_DOORS_DATA_H
static const Mmx6CheckpointCode before_doors_code[]={
    {0x80028078u,0x800280F4u,0xB274C2DAu},
    {0x80030304u,0x8003040Cu,0xEF191854u},
    {0x8003CCBCu,0x8003CD00u,0x55C8676Cu},
    {0x8002A3E8u,0x8002A438u,0x80D6290Cu},
    {0x80029F38u,0x8002A33Cu,0x72A44816u},
    {0x8005211Cu,0x80052300u,0x723008F9u},
    {0x80079230u,0x80079260u,0xD90A93FBu},
    {0x80079290u,0x800792B0u,0x0FCF3C58u},
    {0x80073D50u,0x80073D58u,0x35B5F3CAu},
    {0x8006E27Cu,0x8006E284u,0xB2DFC9D1u},
};
enum { BEFORE_DOORS_LAYOUT=0x80097438u, BEFORE_DOORS_LAYOUT_SIZE=468,
    BEFORE_DOORS_META_SIZE=70144, BEFORE_DOORS_DESC_SIZE=12392 };
#endif
