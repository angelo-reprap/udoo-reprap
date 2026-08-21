# Gulp-Batch Review gulp-batch-20260820-231543

Quelle: `/tmp/gulp-batch-20260820-231543/result.tsv`
DB-TXT: `/tmp/gulp-batch-20260820-231543/source-txt`
Kopiert: 91 Einträge

Pro Person:
- `source/gulp_profil_c.txt` — CRM Rohtext (Quelle)
- `source/AID-*_1.0.0.0.pdf` — Convert-PDF
- `neu/cv/AID-*.pdf` — Pipeline-Ziel
- `extracted/AID-*.txt` — Pipeline-Extrakt
- `extracted/AID-*.pre_json.json` — RAM pre_json (vor DB)
- `extracted/AID-*.db_snapshot.json` — DB nach save (Vergleich)

| Status | Letter/Dir | neu/cv PDF | Quelle TXT |
|--------|------------|------------|------------|
| FAIL | `bbb/behling_karsten` | no_neu_cv | ja |
| OK | `bbb/behnke_marcus` | AID-mb_5.1.4.0.pdf | ja |
| OK | `bbb/biwer_juergen` | AID-jb_2.5.2.0.pdf | ja |
| OK | `bbb/blohm_markus` | AID-mb_5.1.3.0.pdf | ja |
| OK | `bbb/bockemuehl_jens` | AID-jb_1.1.3.0.pdf | ja |
| OK | `bbb/braeutigam_tobias` | AID-tb_5.1.3.0.pdf | ja |
| OK | `bbb/brass_christian` | AID-cb_2.1.3.0.pdf | ja |
| OK | `bbb/buchholz_frank` | AID-fb_4.1.4.0.pdf | ja |
| OK | `ccc/canpolat_goekhan` | AID-gc_4.2.4.0.pdf | ja |
| OK | `ddd/decker_wilfried` | AID-wd_2.1.3.0.pdf | ja |
| OK | `ddd/delatron_dieter` | AID-dd_2.1.5.0.pdf | ja |
| OK | `eee/endras_paul` | AID-pe_3.4.4.0.pdf | ja |
| OK | `eee/engels_christian` | AID-ce_2.1.4.0.pdf | ja |
| OK | `eee/erhardt_frank` | AID-fe_1.1.2.0.pdf | ja |
| OK | `jjj/jourdan_olaf` | AID-oj_1.2.3.0.pdf | ja |
| OK | `fff/faude_dirk` | AID-df_1.1.3.0.pdf | ja |
| OK | `fff/finken_rainer` | AID-rf_4.1.3.0.pdf | ja |
| OK | `fff/frank_juergen` | AID-jf_5.2.4.0.pdf | ja |
| OK | `fff/fuchs_helmut` | AID-hf_1.1.4.0.pdf | ja |
| OK | `fff/funk_gerhard` | AID-gf_5.2.3.0.pdf | ja |
| OK | `ggg/galimova_elena` | AID-eg_2.1.3.0.pdf | ja |
| OK | `ggg/gottfried_guenter` | AID-gg_2.1.3.0.pdf | ja |
| OK | `ggg/gruenberg_patrick` | AID-pg_1.2.2.0.pdf | ja |
| OK | `ggg/gsundbrunn_stefan` | AID-sg_4.1.4.0.pdf | ja |
| OK | `hhh/haefke_jacqueline` | AID-jh_5.3.4.0.pdf | ja |
| OK | `hhh/hanif_mohammed` | AID-mh_5.2.4.0.pdf | ja |
| OK | `hhh/hausherr_hartmann` | AID-hh_4.1.4.0.pdf | ja |
| OK | `hhh/hilbert_joerg` | AID-jh_2.3.2.0.pdf | ja |
| OK | `hhh/homm_jens` | AID-jh_2.3.3.0.pdf | ja |
| OK | `hhh/huettermann_michael` | AID-mh_1.1.3.0.pdf | ja |
| OK | `jjj/jahn_andre` | AID-aj_3.3.4.0.pdf | ja |
| OK | `kkk/kirn_thomas` | AID-tk_1.2.3.0.pdf | ja |
| OK | `kkk/klein_martin` | AID-mk_2.3.2.0.pdf | ja |
| OK | `kkk/klein_stefan` | AID-sk_5.1.3.0.pdf | ja |
| OK | `kkk/knauer_olaf` | AID-ok_4.1.4.0.pdf | ja |
| OK | `kkk/kopshoff_peter` | AID-pk_2.3.3.0.pdf | ja |
| OK | `kkk/koval_alexandre` | AID-ak_2.3.3.0.pdf | ja |
| OK | `kkk/krause_mirko` | AID-mk_2.3.2.0.pdf | ja |
| OK | `kkk/kritchevski_oleg` | AID-ok_4.2.3.0.pdf | ja |
| OK | `kkk/kwasny_marc` | AID-mk_1.1.3.0.pdf | ja |
| OK | `lll/leidel_niko` | AID-nl_5.1.4.0.pdf | ja |
| OK | `lll/lew_joerg` | AID-jl_2.3.3.0.pdf | ja |
| OK | `mmm/maenzel_stefan` | AID-sm_4.1.3.0.pdf | ja |
| OK | `mmm/maerdian_ralf` | AID-rm_2.1.3.0.pdf | ja |
| OK | `mmm/mahmoudy_aziz` | AID-am_2.3.2.0.pdf | ja |
| OK | `mmm/markstaller_michael` | AID-mm_5.2.5.0.pdf | ja |
| OK | `mmm/meese_rainer` | AID-rm_2.1.3.0.pdf | ja |
| OK | `mmm/miersch_joerg` | AID-jm_5.2.4.0.pdf | ja |
| FAIL | `mmm/millonig_roland` | convert | ja |
| OK | `mmm/mohamed_ramadan` | AID-rm_1.1.2.0.pdf | ja |
| OK | `ooo/otto_daniel` | AID-do_1.1.3.0.pdf | ja |
| OK | `ppp/pados_gabor` | AID-gp_1.1.5.0.pdf | ja |
| OK | `ppp/panzer_ralf` | AID-rp_1.1.4.0.pdf | ja |
| FAIL | `ppp/peters_carola` | convert | ja |
| FAIL | `ppp/pfingst_thomas` | convert | ja |
| FAIL | `ppp/pieper_michael` | convert | ja |
| FAIL | `ppp/platt_torsten` | convert | ja |
| FAIL | `ppp/poehlmann_michael` | convert | ja |
| FAIL | `ppp/puchinger_werner` | convert | ja |
| OK | `rrr/rauch_holger` | AID-hr_3.1.4.0.pdf | ja |
| OK | `rrr/richardon_michael` | AID-mr_5.1.4.0.pdf | ja |
| OK | `rrr/richter_levi` | AID-lr_2.3.2.0.pdf | ja |
| OK | `rrr/richter_benjamin` | AID-br_5.2.4.0.pdf | ja |
| FAIL | `rrr/roshop_ulrich` | convert | ja |
| FAIL | `rrr/rubbert_peter` | convert | ja |
| OK | `rrr/runte_oliver` | AID-or_2.3.3.0.pdf | ja |
| OK | `rrr/ryba_rafael` | AID-rr_1.1.3.0.pdf | ja |
| FAIL | `sss/schroeder_wolfgang` | no_neu_cv | ja |
| OK | `sss/seidler_ralf` | AID-rs_4.1.4.0.pdf | ja |
| OK | `sss/seifert_alexander` | AID-as_4.1.3.0.pdf | ja |
| OK | `sss/sjoegren_patrick` | AID-ps_5.1.4.0.pdf | ja |
| OK | `sss/sopart_michael` | AID-ms_1.2.3.0.pdf | ja |
| OK | `sss/soppa_helmut` | AID-hs_1.1.3.0.pdf | ja |
| OK | `sss/sprenger_andre` | AID-as_2.3.3.0.pdf | ja |
| OK | `ttt/tenge_armin` | AID-at_3.3.4.0.pdf | ja |
| OK | `ttt/tezlow_eduard` | AID-et_5.1.3.0.pdf | ja |
| OK | `vvv/van_der_horst_tim` | AID-dv_2.3.2.0.pdf | ja |
| OK | `vvv/vanselow_matthias` | AID-mv_2.3.3.0.pdf | ja |
| OK | `vvv/vogt_uwe` | AID-uv_2.3.2.0.pdf | ja |
| OK | `www/wachniewski_anton` | AID-aw_2.1.4.0.pdf | ja |
| OK | `www/watermann_ulrich` | AID-uw_5.4.4.0.pdf | ja |
| OK | `www/wichmann_uwe` | AID-uw_5.1.4.0.pdf | ja |
| OK | `www/willner-haring_gabor` | AID-gw_3.3.4.0.pdf | ja |
| OK | `www/winkler_ralf` | AID-rw_1.2.3.0.pdf | ja |
| OK | `www/wolters_juergen` | AID-jw_2.3.3.0.pdf | ja |
| OK | `www/wuerthle_mathias` | AID-mw_2.3.2.0.pdf | ja |
| OK | `zzz/zell_peter` | AID-pz_5.1.3.0.pdf | ja |
| OK | `zzz/zimmermann_angelika` | AID-az_2.3.4.0.pdf | ja |
| OK | `zzz/zimmermann_steffen` | AID-sz_2.1.3.0.pdf | ja |
| OK | `zzz/zubok_alexander` | AID-az_2.3.3.0.pdf | ja |
| FAIL | `ggg/glas_oliver_fritz` | no_neu_cv | ja |
