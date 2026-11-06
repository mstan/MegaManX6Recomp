"""Bounded source/typed-policy checks; actual-plugin C fixture is separate."""
import hashlib, json, os, re, struct, tomllib, unittest
from pathlib import Path
import mmx6_host_lab_contract

ROOT=Path(__file__).resolve().parents[1]
PLUGIN=(ROOT/'src/mods/mmx6_coop_plugin.c').read_text(encoding='utf-8')
CHECKPOINT=(ROOT/'src/mods/mmx6_coop_checkpoint.inc').read_text(encoding='utf-8')
SNAPSHOT=(ROOT/'src/mods/mmx6_coop_snapshot.inc').read_text(encoding='utf-8')

def function(text,name):
    start=text.index('static ',text.index(name)-32)
    first=text.index('{',text.index(name));depth=1;end=first+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

class EarnedWeapons(unittest.TestCase):
    def test_lab_only_typed_default(self):
        lab=tomllib.loads((ROOT/'packaging/lab/coop-checkpoint-option.toml').read_text())
        option=next(x for x in lab['option']if x['id']=='lab_earned_weapons')
        self.assertEqual((option['feature'],option['type'],option['default']),('prototype','choice','off'))
        self.assertEqual({x['value']for x in option['choice']},{'off','all'})
        normal=tomllib.loads((ROOT/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text())
        self.assertNotIn('lab_earned_weapons',{x['id']for x in normal['option']})

    def test_native_initializer_authentication(self):
        path=os.environ.get('MMX6_CONTENT_EXE')
        if not path:self.skipTest('Original EXE required')
        data=Path(path).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),'dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046')
        code=data[0x3D718-0x10000+2048:0x3D7AC-0x10000+2048]
        self.assertEqual(hashlib.sha256(code).hexdigest(),'d2cc0660040709245080d3e570746ce3247ec4b9064a251b0a08ce42112e0e8e')
        value=2166136261
        for b in code:value=((value^b)*16777619)&0xffffffff
        self.assertEqual(value,0xE818BDD7)
        stores=[]
        for (word,)in struct.iter_unpack('<I',code):
            if word>>26 in(0x28,0x2B)and (word>>21)&31==5:stores.append(word&0xffff)
        self.assertEqual(stores,[0xE7,0xEC,0xC9,0xC9])
        self.assertNotIn(0x5C,stores);self.assertNotIn(0x93,stores)

    def test_offline_command9_policy_is_exactly_preserved(self):
        # Pin the denial/commit policy itself, independent of a historical
        # Git object that is not part of a staged source checkout.
        def policy(text):
            return re.sub(r'\s+','',re.sub(r'/\*.*?\*/','',text,flags=re.S))
        self.assertEqual(policy(function(PLUGIN,'diagnostic_mutation_allowed')),policy('''
            static int diagnostic_mutation_allowed(void) {
            #ifdef PSX_NO_DEBUG_TOOLS
                return 0;
            #else
                return !psx_mod_netplay_is_active();
            #endif
            }
        '''))
        self.assertEqual(policy(function(PLUGIN,'diagnostic_inventory_setup')),policy('''
            static void diagnostic_inventory_setup(CPUState *cpu) {
                if (psx_mod_read_byte(diagnostic+0x50)!=9) return;
                unsigned mask=psx_mod_read_byte(diagnostic+0x51);
                if (!diagnostic_mutation_allowed() || !mask || scene_owner || zero_projected ||
                    psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
                    psx_mod_read_byte(PLAY+12) || psx_mod_read_byte(PLAY+13) ||
                    psx_mod_read_byte(PLAY+0x38) || psx_mod_read_byte(PLAY+0x5E)!=1 ||
                    life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
                    psx_mod_read_byte(PLAYER+2) || p2.body[2]!=1 ||
                    psx_mod_read_byte(PLAYER+0xE7)!=1 || p2.body[0xE7]!=5 ||
                    psx_mod_read_byte(PLAYER+4)!=1 || p2.body[4]!=1 ||
                    psx_mod_read_byte(PLAYER+5)!=2 || p2.body[5]!=2 ||
                    !checkpoint_equipment_source()) {
                    psx_mod_write_byte(diagnostic+0x50,0);
                    psx_mod_counter_add("mmx6.coop.debug-inventory-rejected",1);
                    return;
                }
            #ifdef MMX6_COOP_INPUT_TAINT_API
                psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX);
            #endif
                checkpoint_equipment_native(cpu,mask);
                psx_mod_write_byte(diagnostic+0x50,0);
                psx_mod_counter_add("mmx6.coop.debug-inventory-grant",1);
            }
        '''))
        self.assertEqual(policy(function(CHECKPOINT,'checkpoint_equipment_source')),policy('''
            static int checkpoint_equipment_source(void) {
                return checkpoint_hash(0x8003D718u,0x8003D7ACu)==0xE818BDD7u;
            }
        '''))

    def test_grant_follows_original_healthy_completion_only(self):
        arm=function(CHECKPOINT,'checkpoint_lab_boundary');body=function(CHECKPOINT,'checkpoint_complete')
        self.assertNotIn('checkpoint_equipment_native',arm);self.assertNotIn('checkpoint_equipment_lab',arm)
        self.assertIn('checkpoint_request(',arm)
        for guard in('checkpoint_lab_authorized()','checkpoint_equipment_source()','checkpoint_before_doors_idle(0)','b[0x5C]!=full','b[0x5D]!=full','b[0x5E]!=full'):
            self.assertLess(body.index(guard),body.index('checkpoint_equipment_lab(cpu)'))
        self.assertLess(body.index('checkpoint_equipment_lab(cpu)'),body.index('checkpoint_earned_weapons_applied=1'))
        self.assertLess(body.index('checkpoint_earned_weapons_applied=1'),body.index('if(hp_pending)'))
        self.assertLess(body.index('checkpoint_earned_weapons_applied=1'),body.index('CHECKPOINT_COMPLETE'))

    def test_lab_restores_campaign_after_both_projection_calls(self):
        body=function(CHECKPOINT,'checkpoint_equipment_lab')
        self.assertIn('campaign=psx_mod_read_byte(PLAY+0x60)',body)
        self.assertIn('STATE_WORDS(restore_campaign,67,&campaign,1)',body)
        self.assertLess(body.index('checkpoint_equipment_native(cpu,0xFFu)'),body.index('psx_mod_write_byte(PLAY+0x60,(uint8_t)campaign)'))
        self.assertLess(body.index('psx_mod_write_byte(PLAY+0x60,(uint8_t)campaign)'),body.index('STATE_POP(restore_campaign)'))

    def test_native_primitive_has_no_body_or_outcome_writes(self):
        body=function(CHECKPOINT,'checkpoint_equipment_native')
        self.assertEqual(body.count('psx_mod_write_'),1)
        self.assertIn('psx_mod_write_byte(PLAY+0x60,(uint8_t)mask)',body)
        self.assertEqual(body.count('guest(cpu,0x8003D718u,PLAYER,0)'),2)
        self.assertIn('enter_zero()',body);self.assertIn('leave_zero()',body)

    def test_reset_snapshot_and_option_identity(self):
        self.assertIn('checkpoint_earned_weapons_option=checkpoint_earned_weapons_applied=checkpoint_earned_weapons_reason=0',CHECKPOINT)
        self.assertIn('checkpoint_earned_weapons_option && !checkpoint_lab_option',CHECKPOINT)
        for s in('s->earned_applied=checkpoint_earned_weapons_applied','FIELD(earned_applied,1,1)',
                  'checkpoint_earned_weapons_applied=s->earned_applied','state_fixed(s,checkpoint_earned_weapons_option)',
                  'state_fixed(s,26)'):
            self.assertIn(s,SNAPSHOT)
        digest=function(SNAPSHOT,'state_digest')
        resources=digest.split('const uint32_t resources[]={',1)[1].split('};',1)[0]
        self.assertIn('checkpoint_earned_weapons_option',resources.split(','))

    def test_current_profile_and_old_title_refusal(self):
        contract=json.loads((ROOT/'docs/COOP_HOST_LAB_CONTRACT.json').read_text())
        header=(ROOT/'src/mods/mmx6_coop_host_lab_contract.h').read_text()
        self.assertEqual(header,mmx6_host_lab_contract.generated_header())
        self.assertIn(f"#define MMX6_HOST_LAB_REVISION {contract['revision']}u",header)
        title=contract['session']['title_compatibility']
        self.assertIn(f'#define MMX6_HOST_LAB_TITLE_COMPATIBILITY "{title}"',header)
        test=(ROOT/'tests/test_mmx6_coop_host_lab.c').read_text()
        self.assertIn(f'.compatibility_id="{title}"',test)
        self.assertIn(f"CHECK(cat.rules->revision=={contract['revision']}&&cat.rules->implementation_count==1)",test)
        self.assertNotEqual(title,'mmx6-x-zero-delay-v37')
        self.assertIn('title.compatibility_id="mmx6-x-zero-delay-v37";CHECK(!lab_title_eligible(&title))',test)
        self.assertIn('MMX6_STARTUP_BUILD_ID=\\"mmx6-x-zero-delay-v67\\"',(ROOT/'CMakeLists.txt').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
