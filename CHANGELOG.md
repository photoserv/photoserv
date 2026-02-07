# Changelog

## [0.9.0](https://github.com/photoserv/photoserv/compare/0.8.0...0.9.0) (2026-02-07)


### Features

* Custom, user-defined attributes on photos and albums ([524ca61](https://github.com/photoserv/photoserv/commit/524ca618a0bccb4434e3f5b6e8c02992fd7a444e))
* Photo geotagging ([524ca61](https://github.com/photoserv/photoserv/commit/524ca618a0bccb4434e3f5b6e8c02992fd7a444e))
* Set entires per-page on tables ([4fda8ef](https://github.com/photoserv/photoserv/commit/4fda8ef5ff6a267182e60932c72684a50c4657d6))


### Bug Fixes

* Better form element spacing for many edit views. ([885cb46](https://github.com/photoserv/photoserv/commit/885cb462247cee998fe4ef743a7554dff7a49b1a))
* Improve image thumbnail formatting in photo list ([aef464d](https://github.com/photoserv/photoserv/commit/aef464db00bc2d0c355d52b826c61ef623a4833c))
* Improve object list header buttons layout on mobile. ([a1c474e](https://github.com/photoserv/photoserv/commit/a1c474eae9e26d000d144bed412e3db1547f0ce0))


### Dependencies

* **js:** bump @alpinejs/sort from 3.15.3 to 3.15.6 ([5747da5](https://github.com/photoserv/photoserv/commit/5747da525fe382d63b0f13d4c268fd8e971ff6cc))
* **js:** bump @codemirror/state from 6.5.3 to 6.5.4 ([bc43780](https://github.com/photoserv/photoserv/commit/bc43780c1e80bba38151fd6aa38bccb74e52d643))
* **js:** bump @codemirror/view from 6.39.7 to 6.39.12 ([25f05e5](https://github.com/photoserv/photoserv/commit/25f05e51dba18f792d417418afee7d5e6b39f396))
* **js:** bump @tailwindcss/cli from 4.1.11 to 4.1.18 ([1414363](https://github.com/photoserv/photoserv/commit/14143634533b32a3f2ef1ebe1167444fd35ecf27))
* **js:** bump alpinejs from 3.15.3 to 3.15.6 ([4e412ab](https://github.com/photoserv/photoserv/commit/4e412abfe0cc8f2e118b48c210d0daff94dfc425))
* **python:** bump celery from 5.5.3 to 5.6.2 ([5d4f6fd](https://github.com/photoserv/photoserv/commit/5d4f6fdcbe4824765a3e9f58ab3cebf844a9fe6b))
* **python:** bump django-crispy-forms from 2.4 to 2.5 ([d6fbe77](https://github.com/photoserv/photoserv/commit/d6fbe77374a550068523ca4c3fd8e5cf1cbd6428))
* **python:** bump gunicorn from 23.0.0 to 24.1.1 ([d2c8cea](https://github.com/photoserv/photoserv/commit/d2c8ceaad30a0fee21e205db1cc8ba63972e53aa))
* **python:** update pillow requirement from &lt;=12.0.0 to &lt;=12.1.0 ([1c124b7](https://github.com/photoserv/photoserv/commit/1c124b7c0d1eb189b6f9c841cdff433c5fd410fc))

## [0.8.0](https://github.com/photoserv/photoserv/compare/0.7.7...0.8.0) (2026-01-18)


### Features

* Album list tree view ([8b4c8d1](https://github.com/photoserv/photoserv/commit/8b4c8d14433d4a0147dd37cea616bac85d02e585))
* Photo calendar ([798cfc4](https://github.com/photoserv/photoserv/commit/798cfc4835506f010687f379763e6e35ed2fe5d0))


### Bug Fixes

* Form field errors display red instead of white ([b84a47b](https://github.com/photoserv/photoserv/commit/b84a47b55fb412c8cda80fc510f10ca96f073886))

## [0.7.7](https://github.com/photoserv/photoserv/compare/0.7.6...0.7.7) (2026-01-07)


### Bug Fixes

* Album manual sort mode ignores asc/desc option ([6661291](https://github.com/photoserv/photoserv/commit/6661291b8b2c99fa5bba430a82aef1a3a40a0f2e))
* Display album sort asc/desc on detail page ([12476d1](https://github.com/photoserv/photoserv/commit/12476d19ddbc39c937036f40084fdaad1314133d))
* Make "descending" the default album sort mode ([b56c096](https://github.com/photoserv/photoserv/commit/b56c0962d8240d07cf298c4bb52322eb42b096de))


### Dependencies

* **js:** bump @alpinejs/sort from 3.15.2 to 3.15.3 ([cc6dae9](https://github.com/photoserv/photoserv/commit/cc6dae9d159ff818351f50d8651f7e0b5c6a1403))
* **js:** bump alpinejs from 3.15.2 to 3.15.3 ([2f5f17e](https://github.com/photoserv/photoserv/commit/2f5f17eaaa43db555c9d803dcd34301ecb9e58b5))
* **js:** bump daisyui from 5.5.8 to 5.5.14 ([57ce872](https://github.com/photoserv/photoserv/commit/57ce872b89d1c68bafe74844d8e22ac8ba1d1068))
* **js:** bump esbuild from 0.27.1 to 0.27.2 ([3a304a8](https://github.com/photoserv/photoserv/commit/3a304a8eb79d0714469ed571db5cc7042c0c7cb3))
* **js:** bump tailwindcss from 4.1.17 to 4.1.18 ([04bd221](https://github.com/photoserv/photoserv/commit/04bd2216fe701517448989e161a0df625892eaf8))
* **python:** bump crispy-daisyui from 0.8.0 to 0.9.0 ([52c7a51](https://github.com/photoserv/photoserv/commit/52c7a5114b418158a9b9d05fa5b6e20e3de2f5c5))
* **python:** bump django from 5.2.4 to 6.0 ([10c562e](https://github.com/photoserv/photoserv/commit/10c562e31b27e2fcc56cd99519e4b8fc13386bc6))
* **python:** bump django-tables2 from 2.7.5 to 2.8.0 ([e7cb815](https://github.com/photoserv/photoserv/commit/e7cb8150059a7b301d8b3d417ec6dfdb858c9252))
* **python:** bump mozilla-django-oidc from 4.0.1 to 5.0.2 ([82706c4](https://github.com/photoserv/photoserv/commit/82706c404a6dc6309dae87afec53257abc3f9c7e))
* **python:** update pillow requirement from &lt;=11.3 to &lt;=12.0.0 ([36bf15c](https://github.com/photoserv/photoserv/commit/36bf15c2b19005daa928d82ce544a10ae74c70f1))

## [0.7.6](https://github.com/photoserv/photoserv/compare/0.7.5...0.7.6) (2026-01-01)


### Bug Fixes

* Better pagination ([29c722e](https://github.com/photoserv/photoserv/commit/29c722e634a5125130f5b55d33b8139e64985e02))
* Photo pagination ([6056298](https://github.com/photoserv/photoserv/commit/6056298b3b410165401e05f2e268430e4336b521))
* Set default publish time for new photos ([eb3a187](https://github.com/photoserv/photoserv/commit/eb3a187ae28a224996e39e4b75b075f44a3ac31a))

## [0.7.5](https://github.com/photoserv/photoserv/compare/0.7.4...0.7.5) (2026-01-01)


### Bug Fixes

* Round publish date to nearest minute ([2d75640](https://github.com/photoserv/photoserv/commit/2d75640f4c89daeca95bd8a504db970d835e3ee8))

## [0.7.4](https://github.com/photoserv/photoserv/compare/0.7.3...0.7.4) (2025-12-31)


### Bug Fixes

* "Get Official Plugins" button moved to bottom of page to improve mobile layout ([76614bf](https://github.com/photoserv/photoserv/commit/76614bfe9251e8c365543bc5e156f3477a1280c1))
* Delete confirmation buttons are full-width on mobile ([edaa789](https://github.com/photoserv/photoserv/commit/edaa78953b72cb40167a34cc87997c56be06a49f))
* Extremely long config sections are now scrollable on Plugin Detail page ([c4b100d](https://github.com/photoserv/photoserv/commit/c4b100d572c511e13f594435d7980b4996647e79))
* Photo form submission not working on Firefox Mobile ([a7f98b4](https://github.com/photoserv/photoserv/commit/a7f98b4007c2a64498ed49a81e756b0c632d78cc))

## [0.7.3](https://github.com/photoserv/photoserv/compare/0.7.2...0.7.3) (2025-12-30)


### Bug Fixes

* Add a link to the project's GitHub in the footer ([5cdb65c](https://github.com/photoserv/photoserv/commit/5cdb65c42d26a3e73bc0f60cd01862236250c651))
* Add support for deleting plugin config keys ([5cdb65c](https://github.com/photoserv/photoserv/commit/5cdb65c42d26a3e73bc0f60cd01862236250c651))
* Display plugin author on detail page ([5cdb65c](https://github.com/photoserv/photoserv/commit/5cdb65c42d26a3e73bc0f60cd01862236250c651))
* Display plugin website on detail page ([5cdb65c](https://github.com/photoserv/photoserv/commit/5cdb65c42d26a3e73bc0f60cd01862236250c651))

## [0.7.2](https://github.com/photoserv/photoserv/compare/0.7.1...0.7.2) (2025-12-27)


### Bug Fixes

* Public API showing unpublished photos ([75d4eb4](https://github.com/photoserv/photoserv/commit/75d4eb46c0aea1b1f57a1cbb06b95b00caecc864))

## [0.7.1](https://github.com/photoserv/photoserv/compare/0.7.0...0.7.1) (2025-12-27)


### Bug Fixes

* Misaligned buttons on mobile ([8f86382](https://github.com/photoserv/photoserv/commit/8f8638225c964d75a4d18db5922c3ecc88507b27))

## [0.7.0](https://github.com/photoserv/photoserv/compare/0.6.4...0.7.0) (2025-12-27)


### Features

* Allow scheduling photos to publish in the future ([2abd809](https://github.com/photoserv/photoserv/commit/2abd80910223fa38cf4eb48f87ba171fdfc8e3f5))
* Dispatch HTTP requests from within Photoserv ([f33d642](https://github.com/photoserv/photoserv/commit/f33d64215332826b07f7b75c4e72eb60897b2040))
* Dispatch publish events manually per-photo ([c945d0f](https://github.com/photoserv/photoserv/commit/c945d0f3c146ffdbff440fa412f676d1a604c750))
* Per-entity plugin parameters ([8759095](https://github.com/photoserv/photoserv/commit/8759095e724e7241cf21231987cad61c9812362d))
* Python plugin integrations ([7bee460](https://github.com/photoserv/photoserv/commit/7bee4607f05d6b71d1422e1639f894ca35a813a5))
* Track and review run logs of integrations. ([2fd4115](https://github.com/photoserv/photoserv/commit/2fd41159d3d4621f7121d6b3d1bdc129c393bdb2))


### Bug Fixes

* Do not attempt to access the database before migrations run when creating initial user ([bc01f08](https://github.com/photoserv/photoserv/commit/bc01f089738c530bc5bb971bb5ecda97b3461ac2))
* Docker compose example image name update ([3c427fb](https://github.com/photoserv/photoserv/commit/3c427fb153e39e8502d1ea6e2bcf5450c9d5ebd7))
* Footer displaying wrong user on users page ([053fbff](https://github.com/photoserv/photoserv/commit/053fbff282a72b420abb2a7afc1745451d5c81d9))
* Make consistency checker run more frequently ([4910e28](https://github.com/photoserv/photoserv/commit/4910e2873e91d677f771d98161778906bdd135c0))
* Persist job results for longer ([a40177b](https://github.com/photoserv/photoserv/commit/a40177bb10527ad20775770a838755d3eb899f08))

## [0.6.4](https://github.com/photoserv/photoserv/compare/0.6.3...0.6.4) (2025-12-04)


### Bug Fixes

* Make dockerfile and CSS compiler look in the right place for Python 3.14 packages ([ba98515](https://github.com/photoserv/photoserv/commit/ba98515bbabd89f4f090fdf874177118ed72435e))

## [0.6.3](https://github.com/photoserv/photoserv/compare/0.6.2...0.6.3) (2025-12-04)


### Bug Fixes

* Configure Dependabot for multiple ecosystems ([d015e16](https://github.com/photoserv/photoserv/commit/d015e169ab217a1ef450b098bc535f127a0656df))
* make publish date auto_now_add ([97acbe7](https://github.com/photoserv/photoserv/commit/97acbe7bee64fbf8e6d1329b090e83a942eb2660))


### Dependencies

* **docker:** bump python from 3.13-slim to 3.14-slim ([3213617](https://github.com/photoserv/photoserv/commit/321361749aceb511378bf386479ded4c8e249424))
* **js:** bump @alpinejs/sort from 3.14.9 to 3.15.2 ([7f94744](https://github.com/photoserv/photoserv/commit/7f94744e67cc9f2a6ab804eb93e6ef2a053942d5))
* **js:** bump alpinejs from 3.14.9 to 3.15.2 ([2a43528](https://github.com/photoserv/photoserv/commit/2a4352817480a502adab5a11661a04e2889a9e02))
* **js:** bump daisyui from 5.0.50 to 5.5.8 ([e306feb](https://github.com/photoserv/photoserv/commit/e306febae653a7ceb2b7b118dd3d38387a0b6163))
* **js:** bump esbuild from 0.25.9 to 0.27.1 ([a903319](https://github.com/photoserv/photoserv/commit/a903319d682839b23caabf77a9b07f2cea8387f5))
* **js:** bump tailwindcss from 4.1.11 to 4.1.17 ([4a71c03](https://github.com/photoserv/photoserv/commit/4a71c032ed8e82a146585a9f743401e595ef3181))
* **python:** bump crispy-daisyui from 0.7.0 to 0.8.0 ([cb63c59](https://github.com/photoserv/photoserv/commit/cb63c5927c50f14da5eeb7900dd51900092bcb28))
* **python:** bump drf-spectacular from 0.28.0 to 0.29.0 ([6da7b16](https://github.com/photoserv/photoserv/commit/6da7b166484b6e523bc16097f7e0eaccf89eca7a))
* **python:** bump psycopg2-binary from 2.9.10 to 2.9.11 ([b198dd8](https://github.com/photoserv/photoserv/commit/b198dd8fa4c69eaa88aae5c543e41aaa76e5c661))
* **python:** bump python-dotenv from 1.1.1 to 1.2.1 ([5c29179](https://github.com/photoserv/photoserv/commit/5c29179f83f89ae96cbba579aeeca4d49fddf5d9))
* **python:** bump redis from 6.4.0 to 7.1.0 ([bcd0178](https://github.com/photoserv/photoserv/commit/bcd01788ea3a02d0edd89eb9e6d253cb27d184df))

## [0.6.2](https://github.com/itsmaxymoo/photoserv/compare/0.6.1...0.6.2) (2025-11-26)


### Bug Fixes

* Do not update photo publish date on edit/save ([30850a5](https://github.com/itsmaxymoo/photoserv/commit/30850a5f772c854eb9d2f67c08e1abed4cda4b10))

## [0.6.1](https://github.com/itsmaxymoo/photoserv/compare/0.6.0...0.6.1) (2025-11-26)


### Bug Fixes

* Add include_sizes query param for /photos, /albums/uuid, /tags/uuid to include photo size data in response ([05e8888](https://github.com/itsmaxymoo/photoserv/commit/05e888819a075de7eec49a02c380558d30e7f812))
* MD5 pending text for photo sizes ([507a8ea](https://github.com/itsmaxymoo/photoserv/commit/507a8eaebc88afbd5e703c105d4016e045e7b054))

## [0.6.0](https://github.com/itsmaxymoo/photoserv/compare/0.5.1...0.6.0) (2025-11-22)


### Features

* Common entity base ([045e82e](https://github.com/itsmaxymoo/photoserv/commit/045e82e1189c7a8c4c06e72a125e472ef5ccd948))
* Return individual picture size information in the public API ([d02d2c9](https://github.com/itsmaxymoo/photoserv/commit/d02d2c9d84386babc537e7186da4047bc0d8925a))

## [0.5.1](https://github.com/itsmaxymoo/photoserv/compare/0.5.0...0.5.1) (2025-10-15)


### Bug Fixes

* 404 error when merging tags ([8c4d037](https://github.com/itsmaxymoo/photoserv/commit/8c4d037d1ee97702c686389652c5dde605eda032))

## [0.5.0](https://github.com/itsmaxymoo/photoserv/compare/0.4.2...0.5.0) (2025-10-10)


### Features

* Consistency checker ([02b983f](https://github.com/itsmaxymoo/photoserv/commit/02b983f64606135471e69b5ef559bc74a9ae10cc))


### Bug Fixes

* Photo sizes not deleted when photo deleted ([aad5770](https://github.com/itsmaxymoo/photoserv/commit/aad5770920273f20deea2da7d8e14c11e11a804b))

## [0.4.2](https://github.com/itsmaxymoo/photoserv/compare/0.4.1...0.4.2) (2025-10-08)


### Bug Fixes

* Album trying to access invalid Photo property ([656f6ff](https://github.com/itsmaxymoo/photoserv/commit/656f6ffbe08f1c669e56b4f7611b3160403b2fa7))
* Styles not persisting from dev to container context ([0ed68c4](https://github.com/itsmaxymoo/photoserv/commit/0ed68c4510c305c1745805855b4bedfb40c975e8))

## [0.4.1](https://github.com/itsmaxymoo/photoserv/compare/0.4.0...0.4.1) (2025-10-08)


### Bug Fixes

* Display images on album order page ([a70fbe6](https://github.com/itsmaxymoo/photoserv/commit/a70fbe6b9586ec4328eb644ccb4e20d3a6e712e9))
* Various styling issues ([50f61aa](https://github.com/itsmaxymoo/photoserv/commit/50f61aacc9e9d2b055f72a8b8d0bf1fe7c33df89))

## [0.4.0](https://github.com/itsmaxymoo/photoserv/compare/0.3.0...0.4.0) (2025-10-06)


### Features

* Better documentation ([5503424](https://github.com/itsmaxymoo/photoserv/commit/550342439bd485bf416f3a108f6fcea949fdd771))
* Create multiple photos at once ([3407f91](https://github.com/itsmaxymoo/photoserv/commit/3407f918cd962d30e43435bd3de5d251c2e1a9eb))
* Jobs overview ([d208deb](https://github.com/itsmaxymoo/photoserv/commit/d208debe805a00df7e4a56881c6f645a6e0ecefa))


### Bug Fixes

* All images falsely displayed as not public ([be5b6e8](https://github.com/itsmaxymoo/photoserv/commit/be5b6e8778f72a4ba5c8fc58f35b7d36c08acacc))
* Borders and styling missing for some form elements ([e6a7e30](https://github.com/itsmaxymoo/photoserv/commit/e6a7e302464610d543331b661788de3627559b35))
* Make sure all core tasks return a message ([3de33e5](https://github.com/itsmaxymoo/photoserv/commit/3de33e5d7822f18dd7c3adf30651dc4c5a3b92fb))
* Pagination no longer scrolls away when tables overflow horizontally ([997a5d5](https://github.com/itsmaxymoo/photoserv/commit/997a5d5bc4f4ba652021af4345a8e116d4223a88))

## [0.3.0](https://github.com/itsmaxymoo/photoserv/compare/0.2.0...0.3.0) (2025-09-30)


### Features

* Add Swagger based API explorer. ([7b92879](https://github.com/itsmaxymoo/photoserv/commit/7b92879b6f3d7780d4e172f22c8cf6b0ca44ec3a))

## [0.2.0](https://github.com/itsmaxymoo/photoserv/compare/0.1.7...0.2.0) (2025-09-26)


### Features

* Add mechanism to hide photos from the public API ([c662f22](https://github.com/itsmaxymoo/photoserv/commit/c662f224464637340eba431d36e87199fbe2b9a1))
* Add support for album parent-child relationship ([c662f22](https://github.com/itsmaxymoo/photoserv/commit/c662f224464637340eba431d36e87199fbe2b9a1))
* Use Postgres 18 by default ([c662f22](https://github.com/itsmaxymoo/photoserv/commit/c662f224464637340eba431d36e87199fbe2b9a1))


### Bug Fixes

* Add /api/health endpoint ([21b0f50](https://github.com/itsmaxymoo/photoserv/commit/21b0f5017d1290fafb1dae8d89c8f4a48551cee7))
* Better EV display in UI ([156e9c0](https://github.com/itsmaxymoo/photoserv/commit/156e9c06704d260219bdfbe3e74d883c677dfb6e))
* Postgres health check throwing root user error ([c662f22](https://github.com/itsmaxymoo/photoserv/commit/c662f224464637340eba431d36e87199fbe2b9a1))

## [0.1.7](https://github.com/itsmaxymoo/photoserv/compare/0.1.6...0.1.7) (2025-09-22)


### Bug Fixes

* DIsplay the status of size generation on the photo detail page ([72a4b06](https://github.com/itsmaxymoo/photoserv/commit/72a4b0652e93e89cc3cc97a645df25625519761c))
* Make layout better on mobile devices ([72a4b06](https://github.com/itsmaxymoo/photoserv/commit/72a4b0652e93e89cc3cc97a645df25625519761c))

## [0.1.6](https://github.com/itsmaxymoo/photoserv/compare/0.1.5...0.1.6) (2025-09-14)


### Bug Fixes

* Add timezone support ([a070dd7](https://github.com/itsmaxymoo/photoserv/commit/a070dd783075e734af324d251303f79f3c262211))
* Increase the default resolution of built-in sizes. ([88ddd0c](https://github.com/itsmaxymoo/photoserv/commit/88ddd0cb70c229c1d0ccec84212bb766ac849cfa))

## [0.1.5](https://github.com/itsmaxymoo/photoserv/compare/0.1.4...0.1.5) (2025-09-13)


### Bug Fixes

* Document OIDC callback URL ([58aaa04](https://github.com/itsmaxymoo/photoserv/commit/58aaa040a1300ffd4a515804e2818211225ca517))
* retrieve EV comp as float ([aba6c48](https://github.com/itsmaxymoo/photoserv/commit/aba6c481703c26221ca08317182d284624c22a40))

## [0.1.4](https://github.com/itsmaxymoo/photoserv/compare/0.1.3...0.1.4) (2025-09-13)


### Bug Fixes

* Run migrations in docker container ([5803676](https://github.com/itsmaxymoo/photoserv/commit/5803676facfa3266dbbb3884111dce6f5e3c42f0))

## [0.1.3](https://github.com/itsmaxymoo/photoserv/compare/v0.1.2...0.1.3) (2025-09-13)


### Bug Fixes

* add manifest ([b0d5d93](https://github.com/itsmaxymoo/photoserv/commit/b0d5d9378993068096d00180704fdd1ea37d5810))
* remove release type from actions def ([384fd08](https://github.com/itsmaxymoo/photoserv/commit/384fd08fcaa2bd9d0bac4499535b69b9a1c8a8be))

## [0.1.2](https://github.com/itsmaxymoo/photoserv/compare/v0.1.1...v0.1.2) (2025-09-13)


### Bug Fixes

* Configure release please (file) ([c1f8b7f](https://github.com/itsmaxymoo/photoserv/commit/c1f8b7ffba83844216e372a1c1e067787751421a))

## [0.1.1](https://github.com/itsmaxymoo/photoserv/compare/v0.1.0...v0.1.1) (2025-09-13)


### Bug Fixes

* Actions: switch to new googleapis namespace ([2d40bd3](https://github.com/itsmaxymoo/photoserv/commit/2d40bd3e40251e147a4d4c3651617382f109ced6))
* Do not include v in image tag ([fcbe002](https://github.com/itsmaxymoo/photoserv/commit/fcbe00288ddc8883b2e730bf27dc9340debc3fd0))

## 0.1.0 (2025-09-13)


### Bug Fixes

* Add documentation; example docker compose file ([10efc08](https://github.com/itsmaxymoo/photoserv/commit/10efc08f2bc8c916c1507fc89920ef296d5ddcef))
