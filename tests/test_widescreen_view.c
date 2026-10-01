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
static PSXModFunctionFilterCallback placement_filter;
static PSXModFunctionFilterCallback fixed_view_filter, ride_armor_filter, npc_start_filter;
static struct { uint32_t pc; PSXModFunctionEntryCallback fn; } hooks[10];
static unsigned hook_count, tag_count, anchor_calls;
static uint32_t tags[8], packet;
static uint8_t object[128];
static uint8_t placement[8], stage, area;
static uint32_t actor_record;
static int camera_x=500, camera_y=944;
static unsigned fixed_view_calls;
static uint32_t fixed_view_radii[2];
static const char *camera_option = "edges";
static const char *aspect_option = "16:9";
static unsigned fixed_num, adaptive_calls;
static int netplay_active, netplay_aspect;
int psx_mod_netplay_is_active(void) { return netplay_active; }
int psx_mod_netplay_aspect(void) { return netplay_aspect; }
static uint32_t scan_state[2], stack_arg=0x1234;
static unsigned scan_calls, world_count;
static int32_t scan_bounds[2][4];
static int (*native_scene)(void);
static uint32_t main_state;
static uint8_t player_state[8];
static unsigned mask_tags;
void gpu_ws_set_native_scene_predicate(int (*p)(void)) { native_scene=p; }
void gpu_ws_tag_screen_mask_quad(uint32_t p) { (void)p; ++mask_tags; }
static uint32_t scan_directions[2];
int mmx6_adaptive_background_activate(void) { return 1; }
void mmx6_adaptive_background_begin(unsigned layer) { assert(layer == 2); }
void mmx6_adaptive_background_end(unsigned layer, uint32_t p) { assert(layer == 2 && p == packet); }
uint32_t psx_mod_alloc_guest_memory(uint32_t n, uint32_t a) { assert(n==8 && a==4); return 0x9f000000u; }
uint16_t psx_mod_read_half(uint32_t p) {
    if (p==0x8009100au || p==0x8009100eu)
        return (uint16_t)(object[p-0x80091000u] | object[p-0x80091000u+1u]<<8);
    if(p==0x80092004u || p==0x80092006u)
        return (uint16_t)(placement[p-0x80092000u] | placement[p-0x80092000u+1u]<<8);
    assert(p==0x80097202u || p==0x80097206u);
    return (uint16_t)(p==0x80097202u ? camera_x : camera_y);
}
void psx_mod_write_word(uint32_t p, uint32_t v) {
    if(p>=0x9f000000u && p<=0x9f000004u) scan_state[(p-0x9f000000u)/4]=v;
    else { assert(p==0x801ffef0u); stack_arg=v; }
}
void psx_mod_write_byte(uint32_t p, uint8_t v) {
    assert(p == 0x80092003u); placement[3] = v;
}
void psx_dispatch_call(CPUState *cpu, uint32_t p, uint32_t r) {
    if(p==0x8002ccb0u) {
        assert(r==cpu->gpr[31]);
        ++fixed_view_calls;
        fixed_view_radii[0]=cpu->gpr[5]; fixed_view_radii[1]=cpu->gpr[6];
        mmx6_actor_view_bounds(cpu,p);
        return;
    }
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
int psx_mod_register_function_filter_plugin(const char *id, uint32_t pc,
                                             PSXModFunctionFilterCallback fn) {
    assert(strcmp(id,"mmx6.widescreen")==0);
    if(pc==0x80029e7cu) placement_filter=fn;
    else if(pc==0x8002cb50u || pc==0x8002cd6cu) fixed_view_filter=fn;
    else if(pc==0x8002cab4u) ride_armor_filter=fn;
    else { assert(pc==0x800f9334u); npc_start_filter=fn; }
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
    if (addr >= 0x800970a0u && addr < 0x800970a8u) return player_state[addr-0x800970a0u];
    if (addr >= 0x8009cad0u && addr < 0x8009cb30u) return object[addr-0x8009cad0u];
    if (addr==0x800ccedcu) return stage;
    if (addr==0x800cceddu) return area;
    if (addr>=0x80092000u && addr<0x80092008u) return placement[addr-0x80092000u];
    if (addr==0x8009200bu) return 15;
    if (addr>=0x8008ef48u && addr<0x8008efc8u) return object[addr-0x8008ef48u];
    assert(addr >= 0x80091000u && addr < 0x80091080u);
    return object[addr - 0x80091000u];
}
uint32_t psx_mod_read_word(uint32_t addr) {
    if (addr==0x800cced0u) return main_state;
    if(addr==0x800734ccu) return 0x80092000u;
    if(addr==0x80091010u) return actor_record;
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
    reveal_margin=566; enter(0x80029d18u,&cpu);
    assert(scan_calls==2 && stack_arg==0x1234);
    assert(scan_bounds[0][0]==868 && scan_bounds[0][1]==1434);
    assert(scan_bounds[1][0]==-114 && scan_bounds[1][1]==452);
    assert(scan_bounds[0][2]==896 && scan_bounds[0][3]==1232);
    assert(scan_directions[0]==1 && scan_directions[1]==2);
    expected.muldiv_ts_done=123;
    assert(!memcmp(&cpu,&expected,sizeof cpu));
    scan_calls=0;
    enter(0x80029d18u,&cpu); assert(scan_calls==2); /* Also stationary. */
    reveal_margin=0; enter(0x80029d18u,&cpu); assert(scan_calls==2);
    /* Original scans stay native. Supplemental scans admit audited visible
     * props and the NPC with a separate sequence gate, never other controllers. */
    for (unsigned category=0;category<8;++category) {
        for (unsigned boss=0;boss<2;++boss) {
            object[3]=(uint8_t)category; object[1]=boss?0x30:2;
            cpu.gpr[4]=0x80091000u; cpu.gpr[2]=0x1234;
            supplemental_scan=0;
            assert(!placement_filter(&cpu,0x80029e7cu) && cpu.gpr[2]==0x1234);
            supplemental_scan=1;
            int deferred=placement_filter(&cpu,0x80029e7cu);
            assert(deferred==((category>=3 && category!=4) || boss));
            assert(cpu.gpr[2]==(deferred?1:0x1234));
        }
    }
    supplemental_scan=0;
    const unsigned visible_types[]={2,8,9,0x30};
    for(stage=0;stage<2;++stage) for(area=0;area<2;++area)
        for(unsigned cat=3;cat<7;++cat) for(unsigned t=0;t<4;++t) {
            object[3]=(uint8_t)cat; object[1]=(uint8_t)visible_types[t]; object[2]=0;
            cpu.gpr[4]=0x80091000u; cpu.gpr[2]=0x1234;
            supplemental_scan=1;
            int intro=!stage&&!area;
            int visible=(cat==4 && (visible_types[t]==8 || (intro&&visible_types[t]==2))) ||
                        (intro && cat==5 && visible_types[t]==8);
            assert(placement_filter(&cpu,0x80029e7cu)==!visible);
        }
    stage=area=0; supplemental_scan=0;
    /* Rain pursuers and generators retain native activation, lifetime and
     * respawn-reset bounds. Ordinary enemies and other stages stay wide. */
    for (stage=5;stage<=6;++stage) for(unsigned type=9;type<=15;++type) {
        object[1]=(uint8_t)type; object[3]=0; object[0x14]=0;
        cpu.gpr[4]=0x8008ef48u; cpu.gpr[5]=64; reveal_margin=566;
        mmx6_actor_view_bounds(&cpu,0x8002cbfcu);
        int native=stage==6 && (type==10 || type==14);
        assert(cpu.gpr[5]==(native?64u:630u));
        cpu.gpr[5]=32; mmx6_actor_view_bounds(&cpu,0x8002ccb0u);
        assert(cpu.gpr[5]==598);
        supplemental_scan=1; assert(placement_filter(&cpu,0x80029e7cu)==native);
        supplemental_scan=0; assert(!placement_filter(&cpu,0x80029e7cu));
    }
    stage=6; area=0; placement[1]=10; placement[4]=0; placement[5]=0;
    placement[6]=0; placement[7]=0;
    for(unsigned active=0;active<2;++active) for(unsigned latch=0;latch<8;++latch) {
        placement[0]=(uint8_t)active; placement[3]=(uint8_t)(latch*16);
        mmx6_reset_native_placements(500,0);
        unsigned expected=latch*16;
        if(!active && (latch==1 || latch==3 || latch==5)) expected+=16;
        assert(placement[3]==expected);
    }
    placement[0]=0; placement[3]=0x10;
    mmx6_reset_native_placements(48,0); assert(placement[3]==0x10); /* Closed edge. */
    stage=area=0;
    /* Fixed-radius draw helpers delegate to the same native wide classifier,
     * preserving their own vertical radii. Off/4:3 and UI keep every register. */
    for(unsigned f=0;f<2;++f) for(unsigned m=0;m<4;++m) for(int selector=-1;selector<3;++selector) {
        memset(&cpu,0,sizeof cpu); cpu.gpr[4]=0x80091000u; cpu.gpr[31]=0x80050e48u;
        object[0x14]=(uint8_t)selector; reveal_margin=margins[m];
        CPUState before=cpu; unsigned calls=fixed_view_calls;
        int handled=fixed_view_filter(&cpu,f?0x8002cd6cu:0x8002cb50u);
        assert(handled==(selector>=0 && reveal_margin>0));
        if(!handled) assert(!memcmp(&before,&cpu,sizeof cpu) && calls==fixed_view_calls);
        else {
            assert(fixed_view_calls==calls+1 && fixed_view_radii[0]==(f?96u:32u));
            assert(fixed_view_radii[1]==(f?80u:32u));
            assert(cpu.gpr[5]==fixed_view_radii[0]+(uint32_t)reveal_margin);
            assert(cpu.gpr[6]==fixed_view_radii[1] && cpu.gpr[31]==before.gpr[31]);
        }
    }
    /* The saved Recycle Lab armor is 78px left of the native camera and was
     * skipped before its widened draw helper. The early gate must admit it at
     * wide aspects without changing 4:3, other objects or vertical reach. */
    memset(object,0,sizeof object); memset(placement,0,sizeof placement);
    stage=4; area=0; actor_record=0x80092000u;
    placement[1]=0x1e; placement[3]=3;
    camera_x=3135; camera_y=224;
    object[10]=0xf1; object[11]=0x0b; /* x=3057 */
    object[14]=0x80; object[15]=0x01; /* y=384 */
    cpu.gpr[4]=0x80091000u; cpu.gpr[2]=0x1234;
    reveal_margin=0;
    assert(!ride_armor_filter(&cpu,0x8002cab4u) && cpu.gpr[2]==0x1234);
    reveal_margin=138;
    assert(ride_armor_filter(&cpu,0x8002cab4u) && cpu.gpr[2]==0);
    object[10]=0xff; object[11]=0x0a; /* x=2815, outside the wide guard */
    assert(ride_armor_filter(&cpu,0x8002cab4u) && cpu.gpr[2]==1);
    object[10]=0xf1; object[11]=0x0b;
    object[14]=0x20; object[15]=0x02; /* y=544, outside vertically */
    assert(ride_armor_filter(&cpu,0x8002cab4u) && cpu.gpr[2]==1);
    object[14]=0x80; object[15]=0x01;
    placement[1]=0x0b; cpu.gpr[2]=0x1234;
    assert(!ride_armor_filter(&cpu,0x8002cab4u) && cpu.gpr[2]==0x1234);
    placement[1]=0x1e;
    stage=0; assert(!ride_armor_filter(&cpu,0x8002cab4u));
    stage=4; object[0x14]=255;
    assert(!ride_armor_filter(&cpu,0x8002cab4u));
    stage=area=0;
    memset(object,0,sizeof object); memset(placement,0,sizeof placement);
    object[1]=placement[1]=8; object[4]=1; placement[3]=5;
    actor_record=0x80092000u; cpu.gpr[4]=0x80091000u;
    placement[4]=6000&255; placement[5]=6000>>8;
    placement[6]=416&255; placement[7]=416>>8;
    const int cam_xs[]={5000,5632,5633,6047,6048};
    const int cam_ys[]={128,129,463,464};
    for(unsigned m=0;m<4;++m) for(unsigned x=0;x<5;++x) for(unsigned y=0;y<4;++y) {
        reveal_margin=margins[m]; camera_x=cam_xs[x]; camera_y=cam_ys[y];
        CPUState before=cpu;
        int outside=6000<=camera_x-48 || 6000>=camera_x+368 ||
                    416<=camera_y-48 || 416>=camera_y+288;
        assert(npc_start_filter(&cpu,0x800f9334u)==outside);
        assert(!memcmp(&before,&cpu,sizeof cpu));
    }
    camera_x=5000; camera_y=300; /* Outside, but unrelated/reused actors stay native. */
    object[2]=1; assert(!npc_start_filter(&cpu,0x800f9334u)); object[2]=0;
    object[5]=1; assert(!npc_start_filter(&cpu,0x800f9334u)); object[5]=0;
    actor_record=0; assert(!npc_start_filter(&cpu,0x800f9334u)); actor_record=0x80092000u;
    stage=1; assert(!npc_start_filter(&cpu,0x800f9334u)); stage=0;
    area=1; assert(!npc_start_filter(&cpu,0x800f9334u)); area=0;
    const char *aspects[] = {"Fit", "16:9", "21:9", "32:9", "old-invalid", NULL};
    const unsigned numerators[] = {16, 16, 21, 32, 16, 16};
    for (unsigned i = 0; i < 6; ++i) {
        hook_count = adaptive_calls = 0;
        aspect_option = aspects[i];
        activate();
        assert(fixed_num == numerators[i]);
        assert(adaptive_calls == (i == 0 || i >= 4));
    }
    main_state=0xa; player_state[0]=player_state[4]=1;
    for(unsigned state=0;state<128;++state) {
        player_state[5]=(uint8_t)state;
        assert(native_scene()==(state==0x4d));
    }
    player_state[5]=0x4d; main_state=0x404; assert(!native_scene());
    main_state=0xa; player_state[4]=2; assert(!native_scene());
    memset(object,0,sizeof object); object[0x37]=255; object[1]=5; object[2]=0x13;
    cpu.gpr[4]=0x8009cad0u;
    for(stage=0;stage<8;++stage) {
        tag_count=0; mask_tags=0; packet=0x800a51b8u;
        enter(0x80023ed8u,&cpu); packet+=0x28; enter(0x80022e44u,&cpu);
        assert(mask_tags==(stage==6));
    }
    stage=6; object[2]=1; mask_tags=tag_count=0;
    enter(0x80023ed8u,&cpu); packet+=0x28; enter(0x80022e44u,&cpu);
    assert(!mask_tags);
    netplay_active = 1;
    camera_option = "centered";
    aspect_option = "Fit";
    for (netplay_aspect = 1; netplay_aspect <= 2; ++netplay_aspect) {
        hook_count = adaptive_calls = anchor_calls = 0;
        activate();
        assert(fixed_num == (netplay_aspect == 1 ? 16u : 21u));
        assert(anchor_calls == 1 && adaptive_calls == 0);
        assert(hook_count == 10 && placement_filter && fixed_view_filter);
    }
    puts("mmx6_widescreen_view: enhanced rendering, guarded actors, and locked netplay views PASS");
    return 0;
}
