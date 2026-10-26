# Submission manifest — October 2026

Submitted 2026-10-25 (V3.1), git tag `2026-10/submitted`, commit 628775c in the imported history.

Layout note: at submission time `code/`, `output.csv`, `output_confidence.csv` and `dataset/` sat side by side in one folder. Here `dataset/` lives at `../data/dataset`; nothing else moved. Files are byte-identical to the submitted ones.

Omitted from this public copy: `.env` (API key), `code.zip` (rebuildable with `code/package.py`), `log.txt` (run log), the session transcript, and fresh model caches (`cache_api`, `cache_final`, `cache_v3`, `cache_live`).

## sha256

```
e7e91998d87224636d7f9f3f76abfe455fc99957db4f01830306c6168b26c1d4  ./.claude/agents/fable-reviewer.md
ee3768cdfa70fa77e57c55813acb07f0a59fc06d4b41718f5510850235044957  ./.env.example
336cc4fbf19beaada7ccf9986414fa91851a8d7a07dfb3ccbe800a69eed0ab49  ./CLAUDE.md
9620e1fc441a19a39e69eed4785b54bea06de1e7ec337290b7d3cc13b8bf511f  ./README.md
f0b2f20d1bc2dcb67c0474d791ee0bce70c2d569b561b455a2dd66c33a743394  ./SUBMISSION_CHECKLIST.md
b6fad6e2cf1319d9eb2b8c97fda44d4df2b3a4bb355116e60ad43d2238ca6d31  ./code/account_rule.py
f813f33b98210e67299d59cbb2bf5c6ab2b2a2ba9d85bbcdf6bc2b1f2aae4700  ./code/cache/intent_cache.json
68a7b3533e172e786c96919ee1c8cdb9ff75c097dd2bc408e30f9fec4099805d  ./code/cache/screenshot_cache.json
1ae047a7b004d71894c292885564e0ac1b2c6166857afc5e073e60e0bf516654  ./code/catalog_rule.py
416c615e27615aa7c51cedd6e87eb991e68ee520ae577447e0b40899a88169c3  ./code/categories.py
f2951625cb9784ab75a2b6a747d6937675c3497086e1df3edefb0f1b007bb9cf  ./code/check_api.py
ab11f32fb92d389a166f845de6490be8ffddb353be05def9575df375343e9fcc  ./code/classify.py
e7cc66dbbbb2ec278c58084fff47bb8ea0ce3fae80d4a1ba97f8624611e156a2  ./code/confidence.py
6fae4a8871b3cfdc6bba140f54be59ad37d184abd8c617f16d0de66b3e0ce0fa  ./code/config.py
f148a6108be7f5454d68248bf1cdc45d86511a057d23b1fa07bbfef7fb7e97b6  ./code/contract.py
812e187f81cf2119029b327caa26089b87ad20b5b0b2d2f28577244ea1feac71  ./code/discover.py
12ff59811d6b6f702998775b0db9c103f9dcf5b0125028ab7bc34964878bd148  ./code/escalate.py
45de3d79ec9987bf079fc762abe8addc2c1994c2c157f0fa3b679ff75dc6d5e1  ./code/evaluation/evaluation_report.md
35593d8832cbe7a815292a1ec6b3dee6cda5bfe3137b685a89d21949e858c718  ./code/evaluation/intent_eval.py
23a241d05e90d21dc9e0c4897e76361d4356345d22980f6737fb87f9a8403664  ./code/evaluation/intent_eval_cases.csv
8abb200fbf4cf6358658dfd4e8ab1b735c2c4bd040c8ad422c701b9c43a6f96e  ./code/evaluation/main.py
aa22b778bce9a3c88a0e1d14d057c0fa19af33f5d6c788f8cb6902dcbd8a5b07  ./code/evaluation/stage_report.py
1a26f8b4cfd947cfbb56f28f2d518ac4b810df5ab9f64182c13f12d8715fdd1e  ./code/evaluation/usage_report.md
458e4fe8bd335baf5428185039f151b7cc461f4ec7957f52a8364fe1e0c21991  ./code/evaluation/usage_summary.py
36639b59abe288a218bb9e197fe8352c38f192116315899cc7507cbb041c6541  ./code/evidence_index.py
38e5f96f1ffff2111096017feb9a46ac23e2a5a24084f033fc28ee162b27dd6c  ./code/evidence_units.py
ceadd8e717b7423b475215842917a96d676cd22fbdcc52d4899597060374d5f7  ./code/identifiers.py
1768287254bc7c7ec6651c69a5f2dd850538eae8b3a4bc103e785902c8ea92d0  ./code/identity.py
aec9429a74ddb9d6d6dab91c94954f2bcbfd6e705bbd6677be87aadfe3ef22e5  ./code/main.py
f82b66fd38893d5fe13fdb43539be7de555e257d58907cc0dbb1c0fb534aca92  ./code/observe.py
2aa175ef90fe8c63787426eb5e14d2d36c8935c33aac106bdc25c0ba262cf4ff  ./code/package.py
c2e631a4f566c07e3eda965467d8bc7fcf43c7d32f78febcadcfe872ac72b22d  ./code/pdf_extract.py
3f8c97a01e371d0825ca59e780f2bd9c5008b4a9386c1d7506680b880dd0840f  ./code/plan.py
9ee9b149a56cc60a285d08df45492c82b3f30e1eb012d837f584b289c0a34e80  ./code/screenshot_extract.py
da513356141ca438fb94c2865a8d9183e2f691bcf7ed2c9ff7ddc91d3cbba429  ./code/server.py
4a3f7da7317472f54bab84e8a7fe4a5d180438411fa2032d979270cf7c039cd2  ./code/state.py
25cad78c5318443b809b29f93cbc592c034ad59c38f301c998085752e08f14d7  ./code/tests/test_account_rule.py
05a6979d34e264586aeb5cf07507b04ef1e61a45ff10d6a6b1122c0416502959  ./code/tests/test_catalog_rule.py
0612ddc284ca6313a7bacebf7e0442f6e0786d066b8658cdc24f15430fa16828  ./code/tests/test_categories.py
2861e15ad970ac1bc4487ee0833eef9f74ad426478f7259685610079cd579569  ./code/tests/test_classify.py
e430ccb998211cbf9484133bba5302196463dbfb986aff4bafca20e2791389f1  ./code/tests/test_confidence.py
22568abed1fcd8891cf3d80b6361c10a8a5490acbbf58fc76cab1f2995b38ec2  ./code/tests/test_config.py
05a722897a4eb70c3238e3d041d091e8bc9f1deb160db3b38ea3866c58620635  ./code/tests/test_evidence_index.py
53d8a0805e80f2ad40501abab6941bc0d7a9656c8b93dda28adda83f7e60f35f  ./code/tests/test_identifiers.py
ddacc35e6f0ab2193d63ad7e858e64dab81155b598fd68ef1722f38a1f49a06e  ./code/tests/test_identity.py
3a54bc64e2abd2ca52d05acc9c87c898d87b5cb1e482493feeaf6244bce3d886  ./code/tests/test_pdf_extract.py
6100811f8210ab678a17e9068bf2ff65749284d2839fbbb06b04e37a8f4d4036  ./code/tests/test_plan.py
3c22798bc914a0e0596eb662bd1ec8cd63cc5dbc70b5d147f892483cb6fcb784  ./code/tests/test_screenshot_extract.py
7cc89e35257dd616dc65351811d0a17d4eceed2a8eda932e56bccef3677c8832  ./code/tests/test_state.py
ed800a83aad8b74f7f8b9c339483602530a32f793d469c2b7ef56fefffadb884  ./code/trace_export.py
adb4069eeb1bcffd9c556acd671f2895ec2678c08978fd3fe5543b569d680e05  ./code/ui/viewer.html
a3144fe0bf963c0f14e200ce3a5c5e379abd4064832893e001cfadcc8dabbc39  ./code/validate_output.py
95487fa9e32219a288cdc5b0c76bfec739e76d4e01fe687969cbfa3b63a3db7d  ./demo/full.html
beecf86d2da19a4e6ceeb70369413f86715b1026914f9d54891d0685640c63a8  ./demo/index.html
024aedf045ef189315cb552616ea5e25a3e0fcc141ce2e0193dca9ec14111d52  ./demo/server.py
6972f8fda077cfcbbc9d59663cf3664eaf8fc539724d2df29c91ec3b78ff4c5b  ./output.csv
27fed1c8c16920b8d9931d86fdf90b0db2968d4795e467807d17dac515656a25  ./output_confidence.csv
72b148770114c8559c7ac2b269d080d75e0077e7fa9af5364d85090ddf451fa4  ./requirements.txt
4cc057e29a6d19e9f3de5d7cbbaf47917cc00523c81e010ce4639f053a76a7b0  ./trace/evaluation_trace.html
3b8900f1231c00d3dceb7c086ea8a176c4b40722fd7b64f5f5248dfae72dc62d  ./trace/sample_trace.html
```
