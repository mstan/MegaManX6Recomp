/* Retail SLUS-01395 object producers share packet storage and OT ranks for
 * dialogue and world props. Exercise the registered hooks with both kinds;
 * an arena/rank-wide UI classification must not pass this regression. */
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdio.h>
#include "../src/mods/mmx6_widescreen_plugin.c"

static PSXModActivationCallback activate;
static struct { uint32_t pc; PSXModFunctionEntryCallback fn; } hooks[10];
static unsigned hook_count, tag_count, anchor_calls;
static uint32_t tags[8], packet;
static uint8_t object[128];
static const char *camera_option = "edges";
static const char *aspect_option = "16:9";
static unsigned fixed_num, adaptive_calls;
static uint32_t scan_state[2], stack_arg=0x1234;
static unsigned scan_calls, world_count;
static int32_t scan_bounds[2][4];
static uint32_t scan_directions[2];
int mmx6_adaptive_background_activate(void) { return 1; }
void mmx6_adaptive_background_begin(unsigned layer) { assert(layer == 2); }
void mmx6_adaptive_background_end(unsigned layer, uint32_t p) { assert(layer == 2 && p == packet); }
uint32_t psx_mod_alloc_guest_memory(uint32_t n, uint32_t a) { assert(n==8 && a==4); return 0x9f000000u; }
uint16_t psx_mod_read_half(uint32_t p) {
    assert(p==0x80097202u || p==0x80097206u); return p==0x80097202u ? 500 : 944;
}
void psx_mod_write_word(uint32_t p, uint32_t v) {
    if(p>=0x9f000000u && p<=0x9f000004u) scan_state[(p-0x9f000000u)/4]=v;
    else { assert(p==0x801ffef0u); stack_arg=v; }
}
void psx_dispatch_call(CPUState *cpu, uint32_t p, uint32_t r) {
    assert(p==0x80029f38u && (r==0x80029d84u || r==0x80029dccu));
    assert(scan_calls<2 && cpu->gpr[29]==0x801ffee0u);
    for(unsigned i=0;i<4;++i) scan_bounds[scan_calls][i]=(int32_t)cpu->gpr[4+i];
    scan_directions[scan_calls++]=stack_arg;
    cpu->gpr[2]=0xdead; cpu->hi=0xbeef; cpu->muldiv_ts_done=123;
}
void psx_mod_tag_world_primitive(uint32_t p, int world) { (void)p; if(world) ++world_count; }
static int32_t reveal_margin;
int32_t psx_mod_widescreen_x_margin(void) { return reveal_margin; }

int psx_mod_register_activation_plugin(const char *id, PSXModActivationCallback fn) {
    assert(strcmp(id, "mmx6.widescreen") == 0);
    activate = fn;
    return 1;
}
int psx_mod_register_function_entry_plugin(const char *id, uint32_t pc,
                                           PSXModFunctionEntryCallback fn) {
    assert(strcmp(id, "mmx6.widescreen") == 0 && hook_count < 10);
    hooks[hook_count].pc = pc; hooks[hook_count++].fn = fn;
    return 1;
}
int psx_mod_option_value(const char *pkg, const char *feature, const char *id,
                         char *out, uint32_t size) {
    assert(strcmp(pkg, PKG) == 0 && strcmp(feature, FEATURE) == 0);
    const char *value = strcmp(id, "camera") == 0 ? camera_option : aspect_option;
    if (!value) return 0;
    assert(strlen(value) < size);
    strcpy(out, value);
    return 1;
}
int psx_mod_set_fixed_display_aspect(uint32_t n, uint32_t d) {
    assert(d == 9); fixed_num = n; return 1;
}
int psx_mod_set_adaptive_display_aspect(uint32_t n, uint32_t d) {
    assert(n == 0 && d == 0); ++adaptive_calls; return 1;
}
uint8_t psx_mod_read_byte(uint32_t addr) {
    assert(addr >= 0x80091000u && addr < 0x80091080u);
    return object[addr - 0x80091000u];
}
uint32_t psx_mod_read_word(uint32_t addr) {
    if(addr>=0x9f000000u && addr<=0x9f000004u) return scan_state[(addr-0x9f000000u)/4];
    if(addr==0x801ffef0u) return stack_arg;
    assert(addr == 0x1f800100u || addr == 0x1f800108u); return packet;
}
void gpu_ws_set_view_anchor(uint32_t camera, uint32_t min, uint32_t max, uint32_t active) {
    assert(camera == 0x80097202u && min == 0x80097216u &&
           max == 0x80097214u && active == 0x800971f8u);
    anchor_calls++;
}
void gpu_ws_bg2d_begin_view_layer(unsigned layer, uint32_t p, unsigned mask) {
    assert(layer == 2 && p == packet && mask == 6);
}
void gpu_ws_bg2d_end_view_layer(unsigned layer, uint32_t p) {
    assert(layer == 2 && p == packet);
}
void gpu_ws_tag_hud_prim(uint32_t p, int anchor) {
    assert(tag_count < 8 && anchor == 0);
    tags[tag_count++] = p;
}
static void enter(uint32_t pc, CPUState *cpu) {
    for (unsigned i = 0; i < hook_count; i++)
        if (hooks[i].pc == pc) { hooks[i].fn(cpu, pc); return; }
    assert(0 && "required generated function-entry hook missing");
}
int main(void) {
    assert(activate);
    activate();
    assert(hook_count == 10 && anchor_calls == 1);
    CPUState cpu = {0};
    cpu.gpr[4] = 2;
    enter(0x800270d0u, &cpu);
    enter(0x80026eccu, &cpu);
    cpu.gpr[4] = 0x80091000u;
    const uint32_t producers[] = {0x800232d4u, 0x800239ccu, 0x80023ed8u, 0x800241d4u};
    for (unsigned i = 0; i < 4; i++) {
        unsigned field = i < 2 ? 0x14 : 0x37;
        unsigned other = i < 2 ? 0x37 : 0x14;
        tag_count = 0; packet = 0x800a51b8u;
        memset(object, 0, sizeof object);
        object[field] = 255;
        enter(producers[i], &cpu); /* Two centered dialogue packets. */
        packet += 2 * 0x28;
        object[field] = 0; object[other] = 255;
        enter(producers[i], &cpu); /* One world prop in the same arena. */
        assert(tag_count == 2 && tags[0] == 0x800a51b8u && tags[1] == 0x800a51e0u);
        packet += 0x28;
        object[field] = 255;
        enter(producers[i], &cpu); /* Last dialogue packet, flushed by driver. */
        assert(tag_count == 2);
        packet += 0x28;
        enter(0x80022e44u, &cpu);
        assert(tag_count == 3 && tags[2] == 0x800a5230u);
        enter(0x80022e44u, &cpu);
        assert(tag_count == 3);
    }
    hook_count = anchor_calls = 0;
    camera_option = "centered";
    activate();
    assert(hook_count == 10 && anchor_calls == 0);
    /* Exercise both shared functions through the registered callback surface.
     * Only the horizontal radius changes; UI and the 4:3 path are identities. */
    const uint32_t bounds[] = {0x8002cbfcu, 0x8002ccb0u};
    const int32_t margins[] = {0, 85, 138, 2048};
    for (unsigned f = 0; f < 2; f++)
        for (unsigned m = 0; m < 4; m++)
            for (int selector = -1; selector <= 2; selector++) {
                memset(&cpu, 0, sizeof cpu);
                cpu.gpr[4] = 0x80091000u;
                cpu.gpr[5] = f == 0 ? 64 : 32;
                cpu.gpr[6] = 32;
                object[0x14] = (uint8_t)selector;
                uint8_t before_object[sizeof object];
                memcpy(before_object, object, sizeof object);
                CPUState expected = cpu;
                reveal_margin = margins[m];
                if (selector >= 0) expected.gpr[5] += margins[m];
                enter(bounds[f], &cpu);
                assert(memcmp(&expected, &cpu, sizeof cpu) == 0);
                assert(memcmp(before_object, object, sizeof object) == 0);
            }
    assert(world_count==4); /* One world prop per retail producer family. */
    memset(&cpu,0,sizeof cpu); cpu.gpr[29]=0x801fff00u;
    CPUState expected=cpu;
    reveal_margin=138; enter(0x80029d18u,&cpu); assert(!scan_calls);
    reveal_margin=566; enter(0x80029d18u,&cpu);
    assert(scan_calls==2 && stack_arg==0x1234);
    assert(scan_bounds[0][0]==958 && scan_bounds[0][1]==1434);
    assert(scan_bounds[1][0]==-114 && scan_bounds[1][1]==362);
    assert(scan_bounds[0][2]==896 && scan_bounds[0][3]==1232);
    assert(scan_directions[0]==1 && scan_directions[1]==2);
    expected.muldiv_ts_done=123;
    assert(!memcmp(&cpu,&expected,sizeof cpu));
    enter(0x80029d18u,&cpu); assert(scan_calls==2);
    reveal_margin=0; enter(0x80029d18u,&cpu); assert(scan_calls==2);
    const char *aspects[] = {"Fit", "16:9", "21:9", "32:9", "old-invalid", NULL};
    const unsigned numerators[] = {16, 16, 21, 32, 16, 16};
    for (unsigned i = 0; i < 6; ++i) {
        hook_count = adaptive_calls = 0;
        aspect_option = aspects[i];
        activate();
        assert(fixed_num == numerators[i]);
        assert(adaptive_calls == (i == 0 || i >= 4));
    }
    puts("mmx6_widescreen_view: adaptive choices, dialogue, actor bounds, vertical/UI/4:3 identity PASS");
    return 0;
}
