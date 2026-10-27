/* SLUS-01395 source guards for the explicit F197/F198 position prerequisite.
 * EXE dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046;
 * BIN2 d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607.
 * Camera records 2/3 supply X max5120 and Y704..704 on this approach.
 * Original subtype1 waits, falls, contacts ground and emits its own explosion
 * and 29478 quake; none of those outcomes is installed by this fixture.
 * No original bytes are distributed. These FNV guards supplement exact pins. */
#ifndef MMX6_COOP_BEFORE_EXPLOSION_DATA_H
#define MMX6_COOP_BEFORE_EXPLOSION_DATA_H
static const Mmx6CheckpointCode before_explosion_code[]={
    {0x80029F38u,0x8002A33Cu,0x72A44816u},
    /* Original lifetime admission: low difficulty0 -> byte3=10 at29EF8;
     * difficulty3 admits without that mutation. SHA256
     * df6eff4115848b712fbc5f13bac169665422de1032a5e9544412af5d56e7da89. */
    {0x80029E7Cu,0x80029F38u,0x45D4158Du},
    {0x8002A3E8u,0x8002A438u,0x80D6290Cu},
    {0x8005211Cu,0x80052300u,0x723008F9u},
    {0x80079210u,0x80079230u,0x8694E1B0u},
    {0x80073D50u,0x80073D58u,0x35B5F3CAu},
    {0x800E9F1Cu,0x800EA1D8u,0x593A7C3Cu},
    {0x800EA1D8u,0x800EA8E0u,0x759777E7u},
    {0x800FA424u,0x800FA428u,0x1B8F615Cu},
    {0x800FA99Cu,0x800FA9A8u,0x3E526D2Eu},
    {0x800FAA34u,0x800FAAC8u,0x3C8369F1u},
};
#endif
