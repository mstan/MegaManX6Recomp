/* Bounded observer of the two existing private draws, including their native
 * clears and fades. The CPU emits immutable scenes; only the GPU owner consumes
 * snapshots/prepares the pair. No callback requests or re-enters guest drawing. */
struct CoopScene {
    Frame frame;
    uint64_t texture=0;
    ~CoopScene(){if(texture)psx_presentation_gpu_release(texture);}
};
struct CoopPair {std::shared_ptr<CoopScene> view[2];uint64_t period_ns=0;};
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
std::unique_ptr<CoopPair> coop_older;
uint64_t coop_rate_pair=0,coop_rate_cycle=0,coop_rate_ready=0;
PairPrepared coop_prepared;
struct CoopOutput {
    uint64_t epoch=0,serial=0,version=0,pair=0,cycle=0,not_before=0,expires=0,deadline=0;
    int crop[2][4]{};
} coop_output;
bool coop_snapshot=false;
// Preserve the first failed pane through PAIR_COMMITTED. The ordinary fallback
// total alone cannot distinguish a missing native marker from rejected data.
const char* coop_first_refusal=nullptr;
const char* coop_reported_refusal=nullptr;
// One retained GPU preparation refusal, distinct from CPU pane capture. Only
// complete old/new pairs may reach this record; startup is not a failure.
const char* coop_first_prepare_refusal=nullptr;
const char* coop_first_select_refusal=nullptr;
bool coop_prepared_once=false;
// One bounded provenance record, protected by native_publication like output.
// Shared native_failure also describes CPU capture and is NOT a GPU result.
struct CoopGpuProvenance {
    const char* prepare="none";
    const char* clear="none";
    PsxPresentationRateRequest request{};
    uint64_t ready=0;
    CoopOutput prior{};
    const char* prior_clear="none";
    uint64_t clear_pair=0,clear_cycle=0,clear_ready=0;
} coop_gpu_provenance;
void native_coop_note_clear(const char* origin,const CoopOutput& prior,
    uint64_t pair,uint64_t cycle,uint64_t ready) {
    coop_gpu_provenance.clear=origin;
    // Later empty clears must not hide the last actual output disposition.
    if(!prior.version)return;
    coop_gpu_provenance.prior=prior;coop_gpu_provenance.prior_clear=origin;
    coop_gpu_provenance.clear_pair=pair;coop_gpu_provenance.clear_cycle=cycle;
    coop_gpu_provenance.clear_ready=ready;
}
void native_coop_prepare_refuse(const char* reason) {
    coop_gpu_provenance.prepare=reason;
    native_failure=reason;
    if(!coop_first_prepare_refusal){
        coop_first_prepare_refusal=reason;
        std::fprintf(stderr,"mmx6 native presentation first pair preparation refusal: %s\n",reason);
    }
}
int native_coop_select_refuse(const char* reason,const CoopOutput& out,
    const PsxPresentationRateRequest& request,uint64_t pair,uint64_t cycle,int w,int h) {
    // Ordinary native boundaries and startup cannot select a scheduled output.
    // Retain only the first refusal AFTER a real private target was prepared.
    if(native_rate && coop_prepared_once) {
        const char* status=native_failure.load();native_failure=reason;
        if(!coop_first_select_refusal) {
            coop_first_select_refusal=reason;
            const auto& gpu=coop_gpu_provenance;
            std::fprintf(stderr,"mmx6 native presentation first pair selection refusal: %s (status=%s out=%llu epoch=%llu/%llu serial=%llu/%llu pair=%llu/%llu/%llu cycle=%llu/%llu/%llu deadline=%llu/%llu start=%llu ready=%llu crop=%d,%d;%d,%d requested=%d,%d gpu_prepare=%s gpu_request=%llu/%llu/%llu/%llu gpu_ready=%llu gpu_clear=%s prior_clear=%s prior=%llu/%llu/%llu/%llu/%llu clear_source=%llu/%llu/%llu)\n",
                reason,status,(unsigned long long)out.version,
                (unsigned long long)out.epoch,(unsigned long long)native_epoch.load(),
                (unsigned long long)out.serial,(unsigned long long)(coop_previous?coop_previous->view[0]->frame.serial:0),
                (unsigned long long)out.pair,(unsigned long long)pair,(unsigned long long)request.pair_id,
                (unsigned long long)out.cycle,(unsigned long long)cycle,(unsigned long long)request.pair_cycle,
                (unsigned long long)out.deadline,(unsigned long long)request.deadline_ns,
                (unsigned long long)request.display_start_ns,(unsigned long long)coop_rate_ready,
                out.crop[0][2],out.crop[0][3],out.crop[1][2],out.crop[1][3],w,h,
                gpu.prepare,(unsigned long long)gpu.request.pair_id,(unsigned long long)gpu.request.pair_cycle,
                (unsigned long long)gpu.request.deadline_ns,(unsigned long long)gpu.request.display_start_ns,
                (unsigned long long)gpu.ready,gpu.clear,gpu.prior_clear,
                (unsigned long long)gpu.prior.version,(unsigned long long)gpu.prior.pair,
                (unsigned long long)gpu.prior.cycle,(unsigned long long)gpu.prior.deadline,
                (unsigned long long)gpu.prior.serial,(unsigned long long)gpu.clear_pair,
                (unsigned long long)gpu.clear_cycle,(unsigned long long)gpu.clear_ready);
        }
    }
    return 0;
}
struct CoopRefusedEffect {
    uint32_t opcode=0,source=0,words=0,invalid=0,pieces=0;
    bool recorded=false;
    uint32_t prefix[4]{};
    uint32_t mode=0;
} coop_first_effect,coop_reported_effect;
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
    coop_first_refusal=coop_reported_refusal=nullptr;
    coop_first_prepare_refusal=nullptr;
    coop_first_select_refusal=nullptr;
    coop_first_effect=coop_reported_effect={};
    std::unique_ptr<CoopPair> release;
    {std::lock_guard<std::mutex> lock(native_publication);release=std::move(coop_previous);coop_older.reset();coop_output={};coop_rate_pair=coop_rate_cycle=coop_rate_ready=0;coop_prepared_once=false;coop_gpu_provenance={};}
}
void native_rate_coop_prepare(const PsxPresentationRateRequest& request) {
    std::lock_guard<std::mutex> lock(native_publication);
    coop_gpu_provenance.request=request;coop_gpu_provenance.ready=coop_rate_ready;
    coop_gpu_provenance.prepare="missing adjacent captured source";
    native_coop_note_clear("prepare",coop_output,request.pair_id,request.pair_cycle,coop_rate_ready);
    coop_output={};
    const auto& old=coop_older;const auto& next=coop_previous;
    if(!old || !next)return;
    if(request.pair_id!=coop_rate_pair || request.pair_cycle!=coop_rate_cycle){
        native_coop_prepare_refuse("native pair request identity");return;
    }
    if(next->view[0]->frame.epoch!=native_epoch){native_coop_prepare_refuse("native pair epoch");return;}
    // next is the latest COMMITTED immutable pair. The CPU can already be
    // building a later world while this pair owns the original output grid.
    const uint64_t period=next->period_ns;
    if(!period || old->period_ns!=period){native_coop_prepare_refuse("native pair period");return;}
    if(request.deadline_ns<=request.display_start_ns || request.deadline_ns>=request.display_start_ns+period){
        native_coop_prepare_refuse("native pair deadline outside source period");return;
    }
    double alpha=0;
    if(!psx_presentation_phase(request.display_start_ns,request.display_start_ns+period,
        coop_rate_ready,request.deadline_ns,&alpha)){
        native_coop_prepare_refuse("native pair phase/source readiness");
        if(coop_rate_ready>request.deadline_ns)coop_gpu_provenance.prepare="source not ready by deadline";
        return;
    }
    if(!coop_prepared.build({&old->view[0]->frame,&old->view[1]->frame},
           {&next->view[0]->frame,&next->view[1]->frame},
           {next->view[0]->texture,next->view[1]->texture},alpha)){
        native_coop_prepare_refuse(coop_prepared.failure);return;
    }
    if(!psx_presentation_gpu_render(coop_prepared.triangles.data(),uint32_t(coop_prepared.triangles.size()),
           coop_prepared.materials.data(),uint32_t(coop_prepared.materials.size()))){
        native_coop_prepare_refuse("native pair binding/private target");return;
    }
    coop_output.epoch=next->view[0]->frame.epoch;coop_output.serial=next->view[0]->frame.serial;
    coop_output.version=psx_presentation_gpu_output_version();coop_output.pair=request.pair_id;
    coop_output.cycle=request.pair_cycle;coop_output.deadline=request.deadline_ns;
    if(coop_output.version)coop_prepared_once=true;
    coop_gpu_provenance.prepare="prepared";
    std::memcpy(coop_output.crop,coop_prepared.crop,sizeof coop_output.crop);++native_ready;native_failure="";
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
        if(view!=native_view || !native_writing || !words || !count || !native_writing->valid || !metadata)return;
        auto& f=*native_writing;f.environment=*env;
        const unsigned op=words[0]>>24;
        if(metadata->invalid || (op>=0x80 && op<=0xDF)){
            // The native GPU already executed this exact command. Only a
            // proven bit-identical copy contributes no visual/material change
            // to this immutable scene. Every other transfer remains refused.
            if(!metadata->invalid && gpu_view_command_is_identity_copy(words,count,env))return;
            if(!coop_first_refusal && !coop_first_effect.recorded){
                coop_first_effect={op,source,count,metadata->invalid,metadata->piece_count,true};
                for(unsigned i=0;i<count && i<4;++i)coop_first_effect.prefix[i]=words[i];
                coop_first_effect.mode=env->mode;
            }
            f.reject("unrepresented native command effect");return;
        }
        const Motion motion=native_packet_motion(source>=4?source-4:source);
        for(unsigned i=0;i<metadata->piece_count && f.valid;++i) {
            const auto& piece=metadata->pieces[i];const auto source_view=f.binding();
            // A draw into a texture target would change later material inputs;
            // the one pre-list snapshot cannot represent that new resource.
            if(op==2 && !piece.wide && (piece.x[0]<source_view.left || piece.x[1]>source_view.right+1 ||
               piece.y[0]<source_view.top || piece.y[2]>source_view.bottom+1)) {
                f.reject("interleaved native texture fill");break;
            }
            if(op!=2 && (piece.clip[1]<int(source_view.top) || piece.clip[3]>int(source_view.bottom) ||
               (!piece.wide && (piece.clip[0]<int(source_view.left) || piece.clip[2]>int(source_view.right))))) {
                f.reject("interleaved native render-to-texture");break;
            }
            f.resolved(piece,motion,metadata->bank,mod_texture_bank_identity(metadata->bank),metadata->live_clut!=0);
        }
    }catch(...) {if(native_writing)native_writing->reject("native pane capture allocation");}
}
void native_coop_ready(void* user) noexcept {
    std::unique_ptr<CoopPair> next(static_cast<CoopPair*>(user));
    try {
        if(!native_enabled || !next->view[0] || !next->view[1] ||
           next->view[0]->frame.epoch!=native_epoch || next->view[1]->frame.epoch!=native_epoch)return;
        native_rate=psx_presentation_gpu_rate_active()!=0;
        {std::lock_guard<std::mutex> lock(native_publication);
        const CoopOutput prior=coop_output;
        coop_output={};
        if(native_rate) {
            GLRenderStereoDiag pair{};gl_renderer_stereo_diag(&pair);
            coop_rate_pair=pair.valid && pair.mode==2?pair.pair_id:0;coop_rate_cycle=pair.guest_cycle;
            coop_rate_ready=rt_now_ns();coop_older=std::move(coop_previous);
            native_coop_note_clear("captured pair",prior,coop_rate_pair,coop_rate_cycle,coop_rate_ready);
            coop_previous=std::move(next);
        }else {
        native_coop_note_clear("ordinary captured pair",prior,0,0,0);
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
        }}
        if(native_rate)psx_presentation_gpu_rate_source_ready();
    }catch(...) {std::lock_guard<std::mutex> lock(native_publication);native_coop_note_clear("capture allocation",coop_output,coop_rate_pair,coop_rate_cycle,coop_rate_ready);coop_output={};++native_fallbacks;native_failure="native pair allocation";}
}
void native_coop_observe(void*,CPUState*,unsigned event,unsigned seat,int complete) {
    try {
        if(event==MMX6_NATIVE_PAIR_CANCEL){native_coop_clear();return;}
        if(!native_enabled || seat>1)return;
        if(event==MMX6_NATIVE_PAIR_COMMITTED) {
            if(coop_writing && coop_writing->view[0] && coop_writing->view[1]) {
                // The original post-VSync producer publishes BOTH private
                // panes each real VBlank, with one adjacent immutable serial.
                coop_writing->period_ns=uint64_t(g_psx_vblank_cycles)*1000000000ull/33868800ull;
                CoopPair* transfer=coop_writing.release();
                if(!psx_presentation_gpu_prepare_async(native_coop_ready,transfer))delete transfer;
            }else{
                coop_writing.reset();++native_fallbacks;
                const char* reason=coop_first_refusal?coop_first_refusal:"native pane observer did not begin";
                native_failure=reason;
                const auto& effect=coop_first_effect;
                if(!coop_reported_refusal || std::strcmp(coop_reported_refusal,reason) ||
                   effect.recorded!=coop_reported_effect.recorded ||
                   effect.opcode!=coop_reported_effect.opcode || effect.invalid!=coop_reported_effect.invalid ||
                   ((effect.mode^coop_reported_effect.mode)&0x1800u)) {
                    std::fprintf(stderr,"mmx6 native presentation first pane refusal: %s (opcode=%02X source=%08X words=%u invalid=%u pieces=%u mode=%08X prefix=%08X,%08X,%08X,%08X)\n",
                        reason,effect.opcode,effect.source,effect.words,effect.invalid,effect.pieces,
                        effect.mode,effect.prefix[0],effect.prefix[1],effect.prefix[2],effect.prefix[3]);
                    coop_reported_refusal=reason;
                    coop_reported_effect=effect;
                }
            }
            return;
        }
        if(event==MMX6_NATIVE_VIEW_BEGIN) {
            if(native_view){native_reject("nested native view");native_coop_restore_capture();return;}
            if(seat==0){coop_writing=std::make_unique<CoopPair>();coop_first_refusal=nullptr;coop_first_effect={};}
            if(!coop_writing)return;
            if(!gpu_view_command_receipt_begin(seat+1)){
                if(!coop_first_refusal)coop_first_refusal="native command scope unavailable";
                return;
            }
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
            f.native_target.left=psx_mod_read_half(native_buffer+0x14);f.native_target.top=psx_mod_read_half(native_buffer+0x16);
            f.native_target.right=f.native_target.left+psx_mod_read_half(native_buffer+0x18)-1;
            f.native_target.bottom=f.native_target.top+psx_mod_read_half(native_buffer+0x1A)-1;f.native_target_set=true;
            coop_current=std::make_shared<CoopScene>();coop_snapshot=false;
        }else if(event==MMX6_NATIVE_VIEW_END && native_view==seat+1) {
            const bool received=gpu_view_command_receipt_end()!=0;
            const bool ok=complete && received && coop_snapshot && native_writing && native_writing->valid &&
                !native_actor_scope.active && native_actor_stack.empty() && !native_bg_scope.active;
            if(ok){coop_current->frame=std::move(*native_writing);coop_writing->view[seat]=coop_current;++native_captured;}
            else if(!coop_first_refusal) {
                coop_first_refusal=!complete?"private drawing incomplete":
                    !native_writing?native_failure.load():
                    !native_writing->valid?native_writing->failure:
                    !received?"native completed-command scope incomplete":
                    !native_complete?"native producer end not observed":
                    !coop_snapshot?"native material snapshot not observed":
                    native_actor_scope.active || !native_actor_stack.empty()?"native actor scope unclosed":
                    native_bg_scope.active?"native background scope unclosed":"native pane incomplete";
            }
            native_coop_restore_capture();

        }
    }catch(...) {native_coop_clear();++native_fallbacks;native_failure="native pane allocation";}
}
int native_coop_present(void*,uint64_t pair,uint64_t cycle,uint64_t present_cycle,int w,int h,
    int repeated,uint64_t* version,int crop[2][4]) {
    if(!native_enabled || (!native_rate && !repeated))return 0;
    PsxPresentationRateRequest request{};
    if(native_rate && !psx_presentation_gpu_rate_request(&request))return 0;
    std::lock_guard<std::mutex> lock(native_publication);
    auto& out=coop_output;
#define SELECT_REFUSE(reason) return native_coop_select_refuse(reason,out,request,pair,cycle,w,h)
    if(!out.version){SELECT_REFUSE("native output unavailable");}
    if(out.epoch!=native_epoch){SELECT_REFUSE("native output epoch");}
    if(!coop_previous){SELECT_REFUSE("native committed pair unavailable");}
    if(out.serial!=coop_previous->view[0]->frame.serial){SELECT_REFUSE("native output serial");}
    if(out.pair!=pair){SELECT_REFUSE("native output pair");}
    if(out.cycle!=cycle){SELECT_REFUSE("native output cycle");}
    if(native_rate?(!request.deadline_ns || request.deadline_ns!=out.deadline):
        (present_cycle<out.not_before || present_cycle>out.expires)){SELECT_REFUSE("native output deadline");}
    if(out.crop[0][2]!=w || out.crop[0][3]!=h || out.crop[1][2]!=w || out.crop[1][3]!=h){SELECT_REFUSE("native output crop");}
    if(!psx_presentation_gpu_output_ready(out.version)){SELECT_REFUSE("native output GPU readiness");}
#undef SELECT_REFUSE
    native_coop_note_clear("selected",out,request.pair_id,request.pair_cycle,coop_rate_ready);
    *version=out.version;std::memcpy(crop,out.crop,sizeof out.crop);out.version=0;native_failure="";++native_presented;return 1;
}
void native_coop_activate() {
    gpu_set_view_command_receipt(native_coop_command,nullptr);
    mmx6_native_coop_set_observer(native_coop_observe,nullptr);
    psx_presentation_gpu_set_pair_provider(native_coop_present,nullptr);
}
