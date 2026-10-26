/* Executable-owned host state, included after the native implementation.
 * Schema 7 is build-specific. No old-state migration or host pointer wire. */
enum { STATE_COUNT,STATE_WRITE,STATE_READ,STATE_HASH,STATE_MAX_BYTES=16*1024*1024 };
typedef struct {
    unsigned mode,ok;
    uint8_t *out;
    const uint8_t *in;
    uint32_t len,pos,hash;
} StateIO;
static void state_bytes(StateIO *s,void *data,uint32_t len) {
    if (!s->ok || len>STATE_MAX_BYTES-s->pos ||
        ((s->mode==STATE_WRITE || s->mode==STATE_READ) && (s->pos>s->len || len>s->len-s->pos))) {
        s->ok=0;return;
    }
    if (s->mode==STATE_WRITE) memcpy(s->out+s->pos,data,len);
    else if (s->mode==STATE_READ) memcpy(data,s->in+s->pos,len);
    else if (s->mode==STATE_HASH) {
        const uint8_t *p=data;
        for (uint32_t i=0;i<len;++i) s->hash=(s->hash^p[i])*16777619u;
    }
    s->pos+=len;
}
static uint32_t state_integer(StateIO *s,uint32_t value,unsigned width,uint32_t max) {
    uint8_t bytes[4];put32(bytes,value);
    state_bytes(s,bytes,width);
    if (s->mode==STATE_READ && s->ok) {
        value=0;for(unsigned i=0;i<width;++i)value|=(uint32_t)bytes[i]<<(i*8);
    }
    if (value>max)s->ok=0;
    return value;
}
static void state_fixed(StateIO *s,uint32_t expected) {
    if (state_integer(s,expected,4,UINT32_MAX)!=expected)s->ok=0;
}
static void snapshot_assets_loaded(const Mmx6AssetView *views,unsigned count) {
    psx_sha256_ctx sha;psx_sha256_init(&sha);
    uint8_t size[4];put32(size,(uint32_t)compressed_size);psx_sha256_update(&sha,size,4);
    psx_sha256_update(&sha,zero_compressed,compressed_size);
    psx_sha256_update(&sha,zero_overlay,sizeof zero_overlay);
    for(unsigned i=0;i<count;++i) {
        put32(size,views[i].type);psx_sha256_update(&sha,size,4);
        put32(size,(uint32_t)views[i].size);psx_sha256_update(&sha,size,4);
        psx_sha256_update(&sha,views[i].data,views[i].size);
    }
    uint8_t pixels[4096];
    for (unsigned base=0;base<1024*512;base+=2048) {
        for(unsigned i=0;i<2048;++i) {
            uint16_t color=zero_ui_pixels[base+i];pixels[i*2]=(uint8_t)color;pixels[i*2+1]=(uint8_t)(color>>8);
        }
        psx_sha256_update(&sha,pixels,sizeof pixels);
    }
    psx_sha256_update(&sha,jump_audio_asset_sha,sizeof jump_audio_asset_sha);
    psx_sha256_final(&sha,snapshot_asset_sha);snapshot_asset_valid=1;
}
static int snapshot_ready(void) {
    if(diagnostic && psx_mod_read_byte(diagnostic+0x50)==8)return 0;
    const unsigned guards[]={inside,player_call,stage_call,zero_world,world_render,
        hud_call,render_x_death,effect_call,pickup_call,solid_call,solid_allocate_call,
        scene_call,zero_projected,unit_choices_call,intro_target_call,shared_fx_call,shared_fx_allocate_call,state_track.count,state_track.error,checkpoint_pending.phase,
        jump_audio_call,jump_audio_keyon_call,jump_audio_stop_call,jump_audio_faulted,
        jump_audio_slot,jump_audio_bank,jump_audio_tone,jump_audio_mode,jump_audio_calculated,jump_audio_stop_mask};
    for(unsigned i=0;i<sizeof guards/sizeof guards[0];++i)if(guards[i])return 0;
    for(unsigned i=0;i<8;++i)if(jump_audio_registers[i])return 0;
    if(!jump_audio_extra_idle())return 0;
    return ready && !failed && jump_audio_ready() && snapshot_asset_valid && zero_compressed && compressed_size && zero_ui_pixels &&
        assets && assembly && palette_source && active_palette && packets && diagnostic && menu_memory &&
        menu_assembly && hud_packets && psx_mod_texture_banks_supported() && !psx_mod_local_view_scope();
}

typedef struct {
    PlayerContext player;
    Mmx6CoopLifecycle lifecycle;
    uint8_t returning[0x158],scene[0x158],portrait[0x200];
    uint32_t join,join_y,owner,scene_phase,scene_y,input,edges,start,menu_loaded;
    uint32_t enrolled,failed,frame_count,hud_fade,world_packets,hud_seat;
    int pause;
    PickupOwner pickups[128];
    SolidContact contacts[SOLID_CONTACTS];
    DeathEffectOrigin deaths[96];
    uint8_t audio_priorities[24];
    uint8_t giga_backup[ZERO_GIGA_BACKUP_BYTES];
    uint8_t shared_owners[96];
} HostState;
static void state_capture(HostState *s) {
    memset(s,0,sizeof *s);s->player=p2;s->lifecycle=life;
    memcpy(s->returning,returning_body,sizeof returning_body);
    memcpy(s->scene,scene_body,sizeof scene_body);
    memcpy(s->portrait,saved_portrait_colors,sizeof saved_portrait_colors);
    s->join=join_phase;s->join_y=(uint32_t)join_y;s->owner=scene_owner;s->scene_phase=scene_phase;s->scene_y=(uint32_t)scene_y;
    s->input=previous_input;s->edges=p2_edges;s->start=p2_start_previous;s->menu_loaded=zero_menu_loaded;s->pause=pause_owner;
    s->enrolled=enrolled;s->failed=failed;s->frame_count=frame_count;s->hud_fade=p2_hud_fade;s->world_packets=world_packets;s->hud_seat=hud_seat;
    memcpy(s->pickups,pickup_owners,sizeof pickup_owners);
    memcpy(s->contacts,zero_solid_contacts,sizeof zero_solid_contacts);
    memcpy(s->deaths,death_effect,sizeof death_effect);
    memcpy(s->audio_priorities,jump_audio_priorities,sizeof jump_audio_priorities);
    memcpy(s->giga_backup,zero_giga_backup,sizeof zero_giga_backup);
    memcpy(s->shared_owners,shared_effect_owners,sizeof shared_effect_owners);
}
static int state_actor(uint32_t address) {
    return !address || (address>=0x80010000u && address<=0x801FFF00u && !(address&3));
}
static int state_assembly(uint32_t address) {
    return (address>=0x80010000u && address<0x80200000u) ||
        (address>=assets && address-assets<ASSET_SPACE);
}
static void state_player(StateIO *io,PlayerContext *p) {
    state_bytes(io,p->body,sizeof p->body);state_bytes(io,p->shots,sizeof p->shots);
    state_bytes(io,p->trails,sizeof p->trails);state_bytes(io,p->effects,sizeof p->effects);
}
static void state_core(StateIO *io,HostState *s) {
#define FIELD(field,width,max) s->field=state_integer(io,(uint32_t)s->field,width,max)
    state_player(io,&s->player);
    FIELD(lifecycle.status[0],1,MMX6_COOP_FALLEN);FIELD(lifecycle.status[1],1,MMX6_COOP_FALLEN);
    FIELD(lifecycle.select_frames,4,90);FIELD(lifecycle.select_armed,1,1);FIELD(lifecycle.select_previous,1,1);
    FIELD(lifecycle.wipe,1,2);FIELD(lifecycle.rejoin_pending,1,1);
    FIELD(join,1,2);FIELD(join_y,4,UINT32_MAX);FIELD(input,2,65535);FIELD(edges,2,65535);
    FIELD(owner,1,2);FIELD(scene_phase,1,5);FIELD(scene_y,4,UINT32_MAX);
    state_bytes(io,s->returning,sizeof s->returning);state_bytes(io,s->scene,sizeof s->scene);
    uint32_t menu=state_integer(io,(uint32_t)(s->pause+1),1,2);s->pause=(int)menu-1;
    FIELD(start,1,1);FIELD(menu_loaded,1,1);state_bytes(io,s->portrait,sizeof s->portrait);
    FIELD(enrolled,1,1);FIELD(failed,1,io->mode==STATE_HASH?1:0);
    state_bytes(io,s->audio_priorities,sizeof s->audio_priorities);
    for(unsigned i=0;i<128;++i) {
        uint32_t actor=state_integer(io,s->pickups[i].actor,4,UINT32_MAX);
        uint32_t seat=state_integer(io,s->pickups[i].actor?s->pickups[i].seat:0,1,1);
        if(!state_actor(actor) || (!actor && seat))io->ok=0;
        s->pickups[i].actor=actor;s->pickups[i].seat=(uint8_t)seat;
        if(actor)for(unsigned j=0;j<i;++j)if(s->pickups[j].actor==actor)io->ok=0;
    }
    for(unsigned i=0;i<SOLID_CONTACTS;++i) {
        FIELD(contacts[i].sides,1,255);FIELD(contacts[i].carried,1,255);
    }
    for(unsigned i=0;i<96;++i) {
        DeathEffectOrigin *o=&s->deaths[i];
        unsigned valid=state_integer(io,o->valid,1,1);o->valid=(uint8_t)valid;
        o->owner=(uint8_t)state_integer(io,o->owner,1,2);
        o->x=state_integer(io,valid?o->x:0,4,UINT32_MAX);
        o->y=state_integer(io,valid?o->y:0,4,UINT32_MAX);
        o->assembly=state_integer(io,valid?o->assembly:0,4,UINT32_MAX);
        o->layer=(uint8_t)state_integer(io,valid?o->layer:0,1,255);
        if(valid && (!o->owner || !state_assembly(o->assembly)))io->ok=0;
    }
    if(!s->owner && s->scene_phase)io->ok=0;
    if(s->lifecycle.rejoin_pending &&
        ((s->lifecycle.status[1]!=MMX6_COOP_ABSENT && s->lifecycle.status[1]!=MMX6_COOP_LEAVING) ||
         !mmx6_coop_living(&s->lifecycle,0) || s->lifecycle.wipe))io->ok=0;
    state_bytes(io,s->giga_backup,sizeof s->giga_backup);
    for(unsigned i=0;i<96;++i)s->shared_owners[i]=(uint8_t)state_integer(io,s->shared_owners[i],1,2);
    if(io->mode!=STATE_HASH) {
        FIELD(frame_count,4,UINT32_MAX);FIELD(hud_fade,1,128);FIELD(world_packets,4,UINT32_MAX);FIELD(hud_seat,1,1);
        if(s->world_packets && (s->world_packets<packets || s->world_packets>packets+FRAME_ARENA*2))io->ok=0;
    }
#undef FIELD
}
static void state_commit(const HostState *s) {
    p2=s->player;life=s->lifecycle;
    memcpy(returning_body,s->returning,sizeof returning_body);memcpy(scene_body,s->scene,sizeof scene_body);
    memcpy(saved_portrait_colors,s->portrait,sizeof saved_portrait_colors);
    join_phase=s->join;join_y=(int32_t)s->join_y;scene_owner=s->owner;scene_phase=s->scene_phase;scene_y=(int32_t)s->scene_y;
    previous_input=(uint16_t)s->input;p2_edges=(uint16_t)s->edges;p2_start_previous=s->start;
    zero_menu_loaded=s->menu_loaded;pause_owner=s->pause;enrolled=s->enrolled;failed=s->failed;
    frame_count=s->frame_count;p2_hud_fade=s->hud_fade;world_packets=s->world_packets;hud_seat=s->hud_seat;
    memcpy(pickup_owners,s->pickups,sizeof pickup_owners);memcpy(zero_solid_contacts,s->contacts,sizeof zero_solid_contacts);
    memcpy(death_effect,s->deaths,sizeof death_effect);
    memcpy(jump_audio_priorities,s->audio_priorities,sizeof jump_audio_priorities);
    memcpy(zero_giga_backup,s->giga_backup,sizeof zero_giga_backup);
    memcpy(shared_effect_owners,s->shared_owners,sizeof shared_effect_owners);
    /* These backups are meaningful only under rejected live projections. */
    memset(&p1,0,sizeof p1);memset(saved_overlay,0,sizeof saved_overlay);memset(saved_play,0,sizeof saved_play);
    memset(saved_camera,0,sizeof saved_camera);memset(saved_resources,0,sizeof saved_resources);saved_palette_dirty=0;
}
static uint32_t state_digest(void) {
    HostState core;state_capture(&core);
    StateIO io={STATE_HASH,1,NULL,NULL,0,0,2166136261u};state_fixed(&io,0x53483658u);state_core(&io,&core);
    const uint32_t resources[]={assets,assembly,palette_source,active_palette,packets,diagnostic,
        menu_memory,menu_assembly,hud_packets,(uint32_t)compressed_size,(unsigned)snapshot_asset_valid,
        jump_audio_banks[0].guest,jump_audio_banks[1].guest,jump_audio_loaded};
    for(unsigned i=0;i<sizeof resources/sizeof resources[0];++i)state_integer(&io,resources[i],4,UINT32_MAX);
    if(snapshot_asset_valid)state_bytes(&io,snapshot_asset_sha,sizeof snapshot_asset_sha);
    const uint32_t guards[]={inside,player_call,stage_call,zero_world,world_render,hud_call,render_x_death,
        effect_call,pickup_call,solid_call,solid_allocate_call,scene_call,zero_projected,unit_choices_call,intro_target_call,shared_fx_call,shared_fx_allocate_call,
        state_track.count,state_track.error,(unsigned)ready,checkpoint_pending.phase,
        checkpoint_pending.index,checkpoint_pending.nonce,jump_audio_call,jump_audio_keyon_call,jump_audio_stop_call,
        jump_audio_slot,jump_audio_bank,jump_audio_tone,jump_audio_mode,jump_audio_calculated,jump_audio_faulted,jump_audio_stop_mask,
        (unsigned)!jump_audio_extra_idle()};
    for(unsigned i=0;i<sizeof guards/sizeof guards[0];++i)state_integer(&io,guards[i],4,UINT32_MAX);
    for(unsigned i=0;i<8;++i)state_integer(&io,jump_audio_registers[i],2,65535);
    if(zero_world)state_integer(&io,world_packets,4,UINT32_MAX);
    if(hud_call)state_integer(&io,hud_seat,1,1);
    if(zero_projected) {
        state_player(&io,&p1);state_bytes(&io,saved_overlay,sizeof saved_overlay);
        state_bytes(&io,saved_play,sizeof saved_play);state_bytes(&io,saved_camera,sizeof saved_camera);
        for(unsigned i=0;i<7;++i)state_integer(&io,saved_resources[i],4,UINT32_MAX);
        state_integer(&io,saved_palette_dirty,1,255);
    }
    for(unsigned i=0;i<state_track.count && i<MMX6_STATE_FRAMES;++i) {
        Mmx6StateFrame *f=&state_track.frame[i];
        state_integer(&io,f->tag,4,UINT32_MAX);state_integer(&io,f->bytes,4,MMX6_STATE_FRAME_BYTES);
        state_integer(&io,f->words,1,1);
        if(f->words)for(unsigned j=0;j<f->bytes;j+=4) {
            uint32_t word;memcpy(&word,f->saved+j,4);state_integer(&io,word,4,UINT32_MAX);
        } else state_bytes(&io,f->saved,f->bytes);
    }
    /* Even rejected/corrupt host state has an explicit non-success domain. */
    unsigned valid=io.ok;io.ok=1;state_integer(&io,valid?0:0xBAD60001u,4,UINT32_MAX);
    return io.hash;
}

typedef struct {
    HostState core;
    SpriteBank sprites[4096];UiBank ui[4096];
    uint32_t sprite_count,ui_count;
    unsigned valid;
} PreparedState;
static PreparedState prepared_state;
static void snapshot_discard_prepared(void) {
    for(unsigned i=0;i<4096;++i) {free(prepared_state.sprites[i].pixels);prepared_state.sprites[i].pixels=NULL;}
    memset(&prepared_state,0,sizeof prepared_state);
}
static void snapshot_resources(StateIO *s) {
    state_fixed(s,0x53503658u);state_fixed(s,7);
    const uint32_t handles[]={assets,assembly,palette_source,active_palette,packets,diagnostic,menu_memory,menu_assembly,hud_packets,
        jump_audio_banks[0].guest,jump_audio_banks[1].guest};
    for(unsigned i=0;i<sizeof handles/sizeof handles[0];++i)state_fixed(s,handles[i]);
    state_fixed(s,(uint32_t)compressed_size);
    uint8_t identity[32];memcpy(identity,snapshot_asset_sha,32);state_bytes(s,identity,32);
    if(s->mode==STATE_READ && memcmp(identity,snapshot_asset_sha,32))s->ok=0;
}
static void snapshot_caches(StateIO *s,PreparedState *prepared) {
    uint32_t count=state_integer(s,bank_count,4,4096);
    if(prepared)prepared->sprite_count=count;
    for(unsigned i=0;i<count && s->ok;++i) {
        SpriteBank b;memset(&b,0,sizeof b);
        if(s->mode!=STATE_READ)b=banks[i];
        b.source=state_integer(s,b.source,4,UINT32_MAX);
        b.id=(uint16_t)state_integer(s,b.id,2,65535);b.tile=(uint16_t)state_integer(s,b.tile,2,65535);
        state_bytes(s,b.colors,32);b.pixel_bytes=state_integer(s,b.pixel_bytes,4,131073);
        uint32_t pixels=b.tile==UINT16_MAX?65536u:256u;
        if(b.id!=0x6000u+i || !b.pixel_bytes || b.pixel_bytes>1+pixels*2)s->ok=0;
        if(s->mode==STATE_READ) {
            if(!s->ok || s->pos>s->len || b.pixel_bytes>s->len-s->pos ||
                !mmx6_pixels_decode(s->in+s->pos,b.pixel_bytes,pixels,NULL)) {s->ok=0;break;}
            b.pixels=malloc(b.pixel_bytes);
            if(!b.pixels) {s->ok=0;break;}
            prepared->sprites[i]=b;
        } else if(!mmx6_pixels_decode(b.pixels,b.pixel_bytes,pixels,NULL)) {s->ok=0;break;}
        state_bytes(s,b.pixels,b.pixel_bytes);
    }
    count=state_integer(s,ui_bank_count,4,4096);
    if(prepared)prepared->ui_count=count;
    for(unsigned i=0;i<count && s->ok;++i) {
        UiBank b;memset(&b,0,sizeof b);if(s->mode!=STATE_READ)b=ui_banks[i];
        b.page=(uint16_t)state_integer(s,b.page,2,65535);b.clut=(uint16_t)state_integer(s,b.clut,2,32767);
        b.uv=(uint16_t)state_integer(s,b.uv,2,65535);b.id=(uint16_t)state_integer(s,b.id,2,65535);
        for(unsigned j=0;j<16;++j)b.colors[j]=(uint16_t)state_integer(s,b.colors[j],2,65535);
        if(b.id!=0x7000u+i || (b.page&0x180u))s->ok=0;
        if(prepared)prepared->ui[i]=b;
    }
}
static uint32_t snapshot_bytes(void) {
    if(!snapshot_ready())return 0;
    HostState core;state_capture(&core);StateIO io={STATE_COUNT,1,NULL,NULL,0,0,0};
    snapshot_resources(&io);state_core(&io,&core);snapshot_caches(&io,NULL);return io.ok?io.pos:0;
}
static int snapshot_write(uint8_t *out,uint32_t len) {
    if(!out || !snapshot_ready() || !len || len>STATE_MAX_BYTES)return 0;
    HostState core;state_capture(&core);StateIO io={STATE_WRITE,1,out,NULL,len,0,0};
    snapshot_resources(&io);state_core(&io,&core);snapshot_caches(&io,NULL);return io.ok && io.pos==len;
}
static int snapshot_validate(const uint8_t *data,uint32_t len) {
    snapshot_discard_prepared();
    if(!data || !len || len>STATE_MAX_BYTES || !snapshot_ready())return 0;
    StateIO io={STATE_READ,1,NULL,data,len,0,0};snapshot_resources(&io);
    state_core(&io,&prepared_state.core);snapshot_caches(&io,&prepared_state);
    if(!io.ok || io.pos!=len) {snapshot_discard_prepared();return 0;}
    prepared_state.valid=1;return 1;
}
static void snapshot_read(const uint8_t *data,uint32_t len) {
    /* SDK promises this exact set passed validation. All fallible allocation
     * and decoding already finished offside; applying it does neither. */
    (void)data;(void)len;
    state_commit(&prepared_state.core);
    for(unsigned i=0;i<4096;++i) {
        free(banks[i].pixels);banks[i]=prepared_state.sprites[i];prepared_state.sprites[i].pixels=NULL;
    }
    bank_count=prepared_state.sprite_count;memcpy(ui_banks,prepared_state.ui,sizeof ui_banks);ui_bank_count=prepared_state.ui_count;
    prepared_state.valid=0;
}
static int snapshot_resolve_texture(uint16_t id) {
    uint16_t pixels[65536];
    if(id>=0x6000u && id<0x6000u+bank_count) {
        const SpriteBank *b=&banks[id-0x6000u];unsigned width=b->tile==UINT16_MAX?256:16;
        return mmx6_pixels_decode(b->pixels,b->pixel_bytes,width*width,pixels) &&
            psx_mod_define_texture_bank(id,width,width,pixels);
    }
    if(id>=0x7000u && id<0x7000u+ui_bank_count && zero_ui_pixels) {
        const UiBank *b=&ui_banks[id-0x7000u];unsigned bx=(b->page&15)*64,by=(b->page&16)*16;
        for(unsigned y=0;y<16;++y)for(unsigned x=0;x<16;++x) {
            unsigned u=((b->uv&255)+x)&255,v=((b->uv>>8)+y)&255;
            unsigned word=zero_ui_pixels[(by+v)*1024+bx+u/4];pixels[y*16+x]=b->colors[(word>>((u&3)*4))&15];
        }
        return psx_mod_define_texture_bank(id,16,16,pixels);
    }
    return 0;
}
static void snapshot_resources_restored(void) {
    /* The validation boundary requires current retained/bound immutable banks.
     * SPU state read preserves their registry/epoch. Rebuild guest headers
     * without allocation, DMA, native calls or changing private DSP state. */
    for(unsigned i=0;i<2;++i)project(jump_audio_banks[i].guest,jump_audio_banks[i].parsed,jump_audio_banks[i].layout.bytes);
    psx_mod_set_texture_bank_resolver(snapshot_resolve_texture);
    if(!psx_mod_forget_texture_bank_range(0x6000u,8192))failed=1;
}
static const PSXModSnapshotProvider snapshot_provider={1,snapshot_bytes,snapshot_write,snapshot_validate,snapshot_read,snapshot_ready};
