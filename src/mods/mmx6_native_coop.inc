/* Bounded observer of the two existing private draws, including their native
 * clears and fades. The CPU emits immutable scenes; only the GPU owner consumes
 * snapshots/prepares the pair. No callback requests or re-enters guest drawing. */
struct CoopScene {
    Frame frame;
    uint64_t texture=0;
    ~CoopScene(){if(texture)psx_presentation_gpu_release(texture);}
};
struct CoopPair {std::shared_ptr<CoopScene> view[2];};
struct SavedCapture {
    uint32_t buffer=0,head=0;
    bool open=false,complete=false,armed=false;
    std::unique_ptr<Frame> frame;
    std::vector<Range> ranges;
    Scope actor{},bg{};
    std::vector<Scope> actor_stack;
} coop_saved;
std::shared_ptr<CoopScene> coop_current;
std::unique_ptr<CoopPair> coop_writing;
std::unique_ptr<CoopPair> coop_previous;
PairPrepared coop_prepared;
struct CoopOutput {
    uint64_t epoch=0,serial=0,version=0,pair=0,cycle=0,not_before=0,expires=0;
    int crop[2][4]{};
} coop_output;
bool coop_snapshot=false;
void native_coop_restore_capture() {
    native_buffer=coop_saved.buffer;native_head=coop_saved.head;
    native_open=coop_saved.open;native_complete=coop_saved.complete;native_armed=coop_saved.armed;
    native_writing=std::move(coop_saved.frame);native_ranges=std::move(coop_saved.ranges);
    native_actor_scope=coop_saved.actor;native_actor_stack=std::move(coop_saved.actor_stack);native_bg_scope=coop_saved.bg;native_view=0;
    coop_current.reset();coop_snapshot=false;
}
void native_coop_clear() {
    psx_presentation_gpu_acquire(); // order lifecycle clear after queued GPU callbacks
    (void)gpu_view_command_receipt_end();
    if(native_view)native_coop_restore_capture();
    coop_writing.reset();
    std::unique_ptr<CoopPair> release;
    {std::lock_guard<std::mutex> lock(native_publication);release=std::move(coop_previous);coop_output={};}
}
void native_coop_ot(CPUState* cpu) {
    if(!coop_current || coop_snapshot || !native_writing || !native_complete ||
       cpu->gpr[4]!=native_buffer+0xECu)return;
    coop_current->texture=psx_presentation_gpu_snapshot_local_view();
    coop_snapshot=coop_current->texture!=0;
    if(!coop_snapshot)native_writing->reject("native pane material snapshot unavailable");
}
void native_coop_command(void*,uint32_t view,uint32_t source,const uint32_t* words,
    uint32_t count,const GpuDrawingEnvironment* env,const GpuViewCommandMetadata* metadata) noexcept {
    try {
        if(view!=native_view || !native_writing || !words || !count || !native_writing->valid)return;
        auto& f=*native_writing;f.environment=*env;
        if(psx_mod_widescreen_view_x_margin()!=0) {f.reject("adaptive view transform not yet bound");return;}
        const size_t first=f.primitives.size();
        const Motion motion=native_packet_motion(source>=4?source-4:source);
        int32_t x[4]{},y[4]{};const int32_t* px=nullptr;const int32_t* py=nullptr;
        const bool host=metadata && metadata->host_tile;
        if(host) {
            const int xx=int16_t(words[1]),yy=Frame::signed11(words[1]>>16);
            for(unsigned j=0;j<4;++j){x[j]=xx+((j&1)?16:0);y[j]=yy+((j&2)?16:0);}px=x;py=y;
        }
        f.add(source,words,count,motion,px,py);
        if(metadata && metadata->bank)f.bank(metadata->bank,mod_texture_bank_identity(metadata->bank),metadata->live_clut!=0,first);
        if(metadata && metadata->mirror_x)
            for(size_t i=first;i<f.primitives.size();++i)
                for(unsigned j=0;j<f.primitives[i].count;++j)
                    f.primitives[i].vertices[j].uv[0]=float(2*(words[2]&255u)+14)-f.primitives[i].vertices[j].uv[0];
    }catch(...) {if(native_writing)native_writing->reject("native pane capture allocation");}
}
void native_coop_ready(void* user) noexcept {
    std::unique_ptr<CoopPair> next(static_cast<CoopPair*>(user));
    try {
        if(!native_enabled || !next->view[0] || !next->view[1] ||
           next->view[0]->frame.epoch!=native_epoch || next->view[1]->frame.epoch!=native_epoch)return;
        std::lock_guard<std::mutex> lock(native_publication);
        coop_output={};
        if(coop_previous && next->view[0]->texture && next->view[1]->texture &&
           coop_prepared.build({&coop_previous->view[0]->frame,&coop_previous->view[1]->frame},
                {&next->view[0]->frame,&next->view[1]->frame},
                {next->view[0]->texture,next->view[1]->texture},.5)) {
            GLRenderStereoDiag native_pair{};gl_renderer_stereo_diag(&native_pair);
            if(native_pair.valid && native_pair.mode==2 &&
               psx_presentation_gpu_render(coop_prepared.triangles.data(),uint32_t(coop_prepared.triangles.size()),
                    coop_prepared.materials.data(),uint32_t(coop_prepared.materials.size()))) {
                coop_output.epoch=next->view[0]->frame.epoch;coop_output.serial=next->view[0]->frame.serial;
                coop_output.version=psx_presentation_gpu_output_version();coop_output.pair=native_pair.pair_id;
                coop_output.cycle=native_pair.guest_cycle;
                coop_output.not_before=native_pair.guest_cycle+g_psx_vblank_cycles/2;
                coop_output.expires=native_pair.guest_cycle+3ull*g_psx_vblank_cycles;
                std::memcpy(coop_output.crop,coop_prepared.crop,sizeof coop_output.crop);
                ++native_ready;native_failure="";
            }else{++native_fallbacks;native_failure="native pair binding/private target";}
        }else{++native_fallbacks;native_failure=!coop_previous?"first native pane pair":coop_prepared.failure;}
        coop_previous=std::move(next);
    }catch(...) {std::lock_guard<std::mutex> lock(native_publication);coop_output={};++native_fallbacks;native_failure="native pair allocation";}
}
void native_coop_observe(void*,CPUState*,unsigned event,unsigned seat,int complete) {
    try {
        if(event==MMX6_NATIVE_PAIR_CANCEL){native_coop_clear();return;}
        if(!native_enabled || seat>1)return;
        if(event==MMX6_NATIVE_PAIR_PREPARED) {
            if(coop_writing && coop_writing->view[0] && coop_writing->view[1]) {
                CoopPair* transfer=coop_writing.release();
                if(!psx_presentation_gpu_prepare_async(native_coop_ready,transfer))delete transfer;
            }else{coop_writing.reset();++native_fallbacks;native_failure="incomplete native pane pair";}
            return;
        }
        if(event==MMX6_NATIVE_VIEW_BEGIN) {
            if(native_view){native_reject("nested native view");native_coop_restore_capture();return;}
            if(seat==0)coop_writing=std::make_unique<CoopPair>();
            if(!coop_writing)return;
            if(!gpu_view_command_receipt_begin(seat+1))return;
            coop_saved.buffer=native_buffer;coop_saved.head=native_head;
            coop_saved.open=native_open;coop_saved.complete=native_complete;coop_saved.armed=native_armed;
            coop_saved.frame=std::move(native_writing);coop_saved.ranges=std::move(native_ranges);
            coop_saved.actor=native_actor_scope;coop_saved.actor_stack=std::move(native_actor_stack);coop_saved.bg=native_bg_scope;
            native_view=seat+1;native_buffer=psx_mod_read_word(0x8009B7A0u);
            native_head=0;native_open=true;native_complete=native_armed=false;
            native_actor_scope={};native_actor_stack.clear();native_bg_scope={};native_ranges.clear();
            native_writing=std::make_unique<Frame>();auto& f=*native_writing;
            f.epoch=native_epoch;f.serial=native_serial;f.tick=native_ticks;
            gpu_get_drawing_environment(&f.environment);f.filter=uint8_t(gr_texture_filter());f.accurate=gl_renderer_accurate_blending()!=0;
            f.target.left=psx_mod_read_half(native_buffer+0x14);f.target.top=psx_mod_read_half(native_buffer+0x16);
            f.target.right=f.target.left+psx_mod_read_half(native_buffer+0x18)-1;
            f.target.bottom=f.target.top+psx_mod_read_half(native_buffer+0x1A)-1;f.target_set=true;
            coop_current=std::make_shared<CoopScene>();coop_snapshot=false;
        }else if(event==MMX6_NATIVE_VIEW_END && native_view==seat+1) {
            const bool received=gpu_view_command_receipt_end()!=0;
            const bool ok=complete && received && coop_snapshot && native_writing && native_writing->valid &&
                !native_actor_scope.active && native_actor_stack.empty() && !native_bg_scope.active;
            if(ok){coop_current->frame=std::move(*native_writing);coop_writing->view[seat]=coop_current;++native_captured;}
            native_coop_restore_capture();

        }
    }catch(...) {native_coop_clear();++native_fallbacks;native_failure="native pane allocation";}
}
int native_coop_present(void*,uint64_t pair,uint64_t cycle,uint64_t present_cycle,int w,int h,
    int repeated,uint64_t* version,int crop[2][4]) {
    if(!native_enabled || !repeated)return 0;
    std::lock_guard<std::mutex> lock(native_publication);
    auto& out=coop_output;
    if(!out.version || out.epoch!=native_epoch || out.serial!=native_serial || out.pair!=pair ||
       out.cycle!=cycle || present_cycle<out.not_before || present_cycle>out.expires ||
       out.crop[0][2]!=w || out.crop[0][3]!=h || out.crop[1][2]!=w || out.crop[1][3]!=h ||
       !psx_presentation_gpu_output_ready(out.version))return 0;
    *version=out.version;std::memcpy(crop,out.crop,sizeof out.crop);out.version=0;++native_presented;return 1;
}
void native_coop_activate() {
    gpu_set_view_command_receipt(native_coop_command,nullptr);
    mmx6_native_coop_set_observer(native_coop_observe,nullptr);
    psx_presentation_gpu_set_pair_provider(native_coop_present,nullptr);
}
