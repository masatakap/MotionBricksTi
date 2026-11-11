"""Offline license viewer. Installed runtime notices remain separate from source notices."""
from functools import lru_cache
from importlib import metadata
from pathlib import Path
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
CREDIT='カスタマイズ　MASATAKA'
PROFILE_URL='https://x.com/masatakaP'
# Customization notice added for Ti; upstream ownership and licenses are unchanged.
RIGHTS_NOTICE={
 'ja':'MotionBricks原著作物の権利はNVIDIA CORPORATION & AFFILIATESに帰属します。第三者のコード・モデル・素材および利用者の制作物の権利は、それぞれの権利者に帰属します。MASATAKAはこれらの原著作物への権利を主張しません。この表記は権利の譲渡や各ライセンスの変更を意味しません。',
 'en':'Rights in the original MotionBricks work belong to NVIDIA CORPORATION & AFFILIATES. Rights in third-party code, models and assets, and user-created works belong to their respective owners. MASATAKA claims no rights in those original works. This notice does not transfer rights or change any applicable license.',
 'es':'Los derechos de la obra original MotionBricks pertenecen a NVIDIA CORPORATION & AFFILIATES. Los derechos del código, modelos y recursos de terceros y de las obras de los usuarios pertenecen a sus respectivos titulares. MASATAKA no reclama derechos sobre esas obras originales. Este aviso no transfiere derechos ni modifica las licencias aplicables.',
 'fr':'Les droits sur l’œuvre originale MotionBricks appartiennent à NVIDIA CORPORATION & AFFILIATES. Les droits sur le code, les modèles et les ressources tiers ainsi que les créations des utilisateurs appartiennent à leurs titulaires respectifs. MASATAKA ne revendique aucun droit sur ces œuvres originales. Cette mention ne transfère aucun droit et ne modifie aucune licence applicable.',
 'zh':'MotionBricks原始作品的权利归NVIDIA CORPORATION & AFFILIATES所有。第三方代码、模型、素材及用户作品的权利归各自权利人所有。MASATAKA不对这些原始作品主张权利。本声明不构成权利转让，也不改变任何适用许可。',
}
CUSTOM_RIGHTS={
 'ja':'MASATAKAが権利を持つ追加・変更部分と自作モーキャプの動作曲線は、対象一覧の範囲でCC0 1.0を適用します。第三者のコード・骨格・モデル・音楽等は対象外です。NVIDIAへの権利譲渡を意味しません。詳細は構成要素の「MASATAKA — CC0 contribution scope」を参照してください。',
 'en':'CC0 1.0 applies to MASATAKA-owned additions, changes and captured motion curves within the listed scope. Third-party code, skeletons, models and music are excluded. No rights are assigned to NVIDIA. See MASATAKA — CC0 contribution scope below.',
 'es':'CC0 1.0 se aplica a las aportaciones y curvas capturadas propiedad de MASATAKA dentro del alcance indicado. Se excluyen código, esqueletos, modelos y música de terceros. No se ceden derechos a NVIDIA. Consulte MASATAKA — CC0 contribution scope.',
 'fr':'CC0 1.0 s’applique aux contributions et courbes capturées appartenant à MASATAKA dans le périmètre indiqué. Code, squelettes, modèles et musique tiers sont exclus. Aucun droit n’est cédé à NVIDIA. Consultez MASATAKA — CC0 contribution scope.',
 'zh':'在清单范围内，MASATAKA拥有权利的新增、修改部分及自制动作捕捉曲线采用CC0 1.0。第三方代码、骨架、模型及音乐等除外，不表示向NVIDIA转让权利。详见下方MASATAKA — CC0 contribution scope。',
}
AUTODESK_ATTRIBUTION=(ROOT/'app/native/README.md').read_text(encoding='utf-8').split('## Autodesk attribution',1)[1].strip()
LABELS={
 'en':('Licenses & Credits','Component','Open website','Close'),
 'ja':('ライセンス・クレジット','構成要素','関連サイトを開く','閉じる'),
 'es':('Licencias y créditos','Componente','Abrir sitio web','Cerrar'),
 'fr':('Licences et crédits','Composant','Ouvrir le site web','Fermer'),
 'zh':('许可与致谢','组件','打开相关网站','关闭'),
}
SUMMARY={
 'ja':'原作 MotionBricks：NVIDIA CORPORATION & AFFILIATES。コードはApache 2.0、ドキュメント等はCC BY 4.0（個別条件のある素材を除く）。ONNXモデルはNVIDIA Open Model Agreementで、同梱ファイルに表示されたリンク先が契約本文です。同梱モーションはBones RigPlay 1由来で、NVIDIA Sample Data Evaluation Licenseによる内部評価・テスト用途に限定され、サンプルや派生物の再配布は認められていません。Inter／Noto Sans JP／Noto Sans SCはSIL OFL 1.1です。MP4用FFmpeg実行ファイルはGPL v3以降、imageio-ffmpegラッパーはBSD 2-Clauseです。TensorRT・CUDAの実行時パッケージにはNVIDIA独自の条件が適用され、TensorRT OSSのライセンスとは別です。本表示は公開配布に必要な条件をすべて満たしたことを示すものではありません。Tiは独自拡張でありNVIDIA公式製品ではありません。下で原文とインストール済み依存ライブラリの表記を確認できます。',
 'en':'Original MotionBricks: NVIDIA CORPORATION & AFFILIATES. Source code: Apache 2.0; documentation and other materials: CC BY 4.0, except assets with separate terms. ONNX models use the NVIDIA Open Model Agreement; the bundled notice links to the agreement. Bundled motions derive from Bones RigPlay 1 and use the NVIDIA Sample Data Evaluation License: internal evaluation/testing only; redistribution of samples or derivatives is prohibited. Inter, Noto Sans JP and Noto Sans SC use SIL OFL 1.1. The MP4 FFmpeg executable uses GPL v3 or later; the imageio-ffmpeg wrapper uses BSD 2-Clause. TensorRT/CUDA runtime packages have separate NVIDIA proprietary terms, distinct from TensorRT OSS. This display does not establish that all public-distribution requirements are satisfied. Ti is an independent extension, not an official NVIDIA product. Original notices and installed runtime dependencies are available below.',
 'es':'MotionBricks original: NVIDIA CORPORATION & AFFILIATES. Código: Apache 2.0; documentación y otros materiales: CC BY 4.0, salvo recursos con condiciones propias. Los modelos ONNX usan NVIDIA Open Model Agreement; el aviso incluido enlaza al contrato. Las muestras de movimiento proceden de Bones RigPlay 1: NVIDIA Sample Data Evaluation License permite solo evaluación y pruebas internas, sin redistribuir muestras ni derivados. Inter, Noto Sans JP y Noto Sans SC: SIL OFL 1.1. El ejecutable FFmpeg usa GPL v3 o posterior; imageio-ffmpeg usa BSD 2-Clause. Los paquetes de ejecución TensorRT/CUDA tienen condiciones propietarias de NVIDIA, distintas de TensorRT OSS. Esta pantalla no confirma el cumplimiento de todos los requisitos de distribución pública. Ti es una extensión independiente, no un producto oficial de NVIDIA. Consulte los avisos originales y las dependencias instaladas a continuación.',
 'fr':'MotionBricks original : NVIDIA CORPORATION & AFFILIATES. Code : Apache 2.0 ; documentation et autres éléments : CC BY 4.0, sauf ressources sous conditions distinctes. Les modèles ONNX relèvent du NVIDIA Open Model Agreement ; la notice fournie renvoie au contrat. Les mouvements proviennent de Bones RigPlay 1 : la NVIDIA Sample Data Evaluation License autorise uniquement les évaluations et tests internes, sans redistribution des échantillons ni de leurs dérivés. Inter, Noto Sans JP et Noto Sans SC : SIL OFL 1.1. FFmpeg utilise GPL v3 ou ultérieure ; imageio-ffmpeg utilise BSD 2-Clause. Les paquets TensorRT/CUDA sont soumis aux conditions propriétaires NVIDIA, distinctes de TensorRT OSS. Cet écran ne confirme pas le respect de toutes les exigences de distribution publique. Ti est une extension indépendante, pas un produit officiel NVIDIA. Notices originales et dépendances installées ci-dessous.',
 'zh':'原版MotionBricks：NVIDIA CORPORATION & AFFILIATES。代码采用Apache 2.0，文档等采用CC BY 4.0，另有条款的资源除外。ONNX模型采用NVIDIA Open Model Agreement，附带说明中的链接指向协议正文。示例动作来自Bones RigPlay 1，采用NVIDIA Sample Data Evaluation License，仅限内部评估和测试，禁止重新分发示例及其衍生物。Inter、Noto Sans JP和Noto Sans SC采用SIL OFL 1.1。MP4所用FFmpeg程序采用GPL v3或更高版本，imageio-ffmpeg封装采用BSD 2-Clause。TensorRT和CUDA运行时包适用NVIDIA专有条款，与TensorRT OSS许可不同。本页面不表示已满足公开分发的全部要求。Ti是独立扩展，并非NVIDIA官方产品。下方可查看原始声明及已安装依赖库。',
}



# Keep the original notice available for a deliberate private restore.
if (ROOT/'assets/motions/REMOVED_SAMPLES.json').is_file():
    SUMMARY.update({'ja': '原作 MotionBricks：NVIDIA CORPORATION & AFFILIATES。コードはApache 2.0、ドキュメント等はCC BY 4.0（個別条件のある素材を除く）。ONNXモデルはNVIDIA Open Model Agreementで、同梱ファイルに表示されたリンク先が契約本文です。原版の評価用モーションと、そのデータを参照する保存物はこの版の配布対象から削除済みです。改訂版と利用者制作モーションの利用条件は、各データの出典・クレジットと下記原文を確認してください。Inter／Noto Sans JP／Noto Sans SCはSIL OFL 1.1です。MP4用FFmpeg実行ファイルはGPL v3以降、imageio-ffmpegラッパーはBSD 2-Clauseです。TensorRT・CUDAの実行時パッケージにはNVIDIA独自の条件が適用され、TensorRT OSSのライセンスとは別です。本表示は公開配布に必要な条件をすべて満たしたことを示すものではありません。Tiは独自拡張でありNVIDIA公式製品ではありません。下で原文とインストール済み依存ライブラリの表記を確認できます。', 'en': 'Original MotionBricks: NVIDIA CORPORATION & AFFILIATES. Source code: Apache 2.0; documentation and other materials: CC BY 4.0, except assets with separate terms. ONNX models use the NVIDIA Open Model Agreement; the bundled notice links to the agreement. The original evaluation-only motion samples and saved documents referencing them have been removed from this distribution. Revised and user-created motions retain their own source terms and credits; consult each asset and the notices below. Inter, Noto Sans JP and Noto Sans SC use SIL OFL 1.1. The MP4 FFmpeg executable uses GPL v3 or later; the imageio-ffmpeg wrapper uses BSD 2-Clause. TensorRT/CUDA runtime packages have separate NVIDIA proprietary terms, distinct from TensorRT OSS. This display does not establish that all public-distribution requirements are satisfied. Ti is an independent extension, not an official NVIDIA product. Original notices and installed runtime dependencies are available below.', 'es': 'MotionBricks original: NVIDIA CORPORATION & AFFILIATES. Código: Apache 2.0; documentación y otros materiales: CC BY 4.0, salvo recursos con condiciones propias. Los modelos ONNX usan NVIDIA Open Model Agreement; el aviso incluido enlaza al contrato. Las muestras originales de movimiento para evaluación y los documentos guardados que las referencian se han retirado de esta distribución. Los movimientos revisados y del usuario conservan sus propios créditos y condiciones de origen. Inter, Noto Sans JP y Noto Sans SC: SIL OFL 1.1. El ejecutable FFmpeg usa GPL v3 o posterior; imageio-ffmpeg usa BSD 2-Clause. Los paquetes de ejecución TensorRT/CUDA tienen condiciones propietarias de NVIDIA, distintas de TensorRT OSS. Esta pantalla no confirma el cumplimiento de todos los requisitos de distribución pública. Ti es una extensión independiente, no un producto oficial de NVIDIA. Consulte los avisos originales y las dependencias instaladas a continuación.', 'fr': 'MotionBricks original : NVIDIA CORPORATION & AFFILIATES. Code : Apache 2.0 ; documentation et autres éléments : CC BY 4.0, sauf ressources sous conditions distinctes. Les modèles ONNX relèvent du NVIDIA Open Model Agreement ; la notice fournie renvoie au contrat. Les échantillons de mouvement d’évaluation et les documents enregistrés qui les référencent ont été retirés de cette distribution. Les mouvements révisés et créés par l’utilisateur conservent leurs crédits et conditions propres. Inter, Noto Sans JP et Noto Sans SC : SIL OFL 1.1. FFmpeg utilise GPL v3 ou ultérieure ; imageio-ffmpeg utilise BSD 2-Clause. Les paquets TensorRT/CUDA sont soumis aux conditions propriétaires NVIDIA, distinctes de TensorRT OSS. Cet écran ne confirme pas le respect de toutes les exigences de distribution publique. Ti est une extension indépendante, pas un produit officiel NVIDIA. Notices originales et dépendances installées ci-dessous.', 'zh': '原版MotionBricks：NVIDIA CORPORATION & AFFILIATES。代码采用Apache 2.0，文档等采用CC BY 4.0，另有条款的资源除外。ONNX模型采用NVIDIA Open Model Agreement，附带说明中的链接指向协议正文。本发行版已移除原版仅供评估的动作样本及引用它们的已保存文档。修订动作和用户制作动作各有来源条款与署名，请查看各项资源及下方原文。Inter、Noto Sans JP和Noto Sans SC采用SIL OFL 1.1。MP4所用FFmpeg程序采用GPL v3或更高版本，imageio-ffmpeg封装采用BSD 2-Clause。TensorRT和CUDA运行时包适用NVIDIA专有条款，与TensorRT OSS许可不同。本页面不表示已满足公开分发的全部要求。Ti是独立扩展，并非NVIDIA官方产品。下方可查看原始声明及已安装依赖库。'})

@lru_cache(maxsize=1)
def catalog():
    entries=[]
    def add(name,paths,url=''):
        entries.append((name,tuple(Path(p) for p in paths),url))
    add('MotionBricks — Apache 2.0 / CC BY 4.0',[ROOT/'LICENSE'],'https://github.com/NVlabs/MotionBricks')
    add('ONNX — NVIDIA Open Model Agreement',[ROOT/'motionbricks/assets/onnx/LICENSE.md'],
        'https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-agreement/')
    add('Sample motions — NVIDIA Sample Data Evaluation License',
        [ROOT/'assets/motions/LICENSE.txt',ROOT/'assets/motions/README.md'])
    add('Fonts — SIL OFL 1.1',[ROOT/'app/fonts/README.md',ROOT/'app/fonts/Inter-OFL.txt',ROOT/'app/fonts/NotoSansJP-OFL.txt'])
    add('FFmpeg executable — GPL v3 or later',[ROOT/'licenses/ffmpeg-GPL-3.0.txt'],'https://www.gyan.dev/ffmpeg/builds/')
    add('Autodesk FBX SDK 2020.3.11 — Autodesk License and Services Agreement',
        [ROOT/'licenses/Autodesk-FBX-SDK-2020.3.11-LICENSE.txt',ROOT/'licenses/Autodesk-FBX-third-party-NOTICES.txt',ROOT/'app/native/README.md'],
        'https://aps.autodesk.com/developer/overview/fbx-sdk')
    for path in sorted((ROOT/'licenses').glob('*.txt')):
        if path.name=='ffmpeg-GPL-3.0.txt' or path.name.startswith('Autodesk-FBX-'):continue
        add('Source notice: '+path.stem,[path])
    add('Kimodo SOMA77 static axis calibration — Apache 2.0',[ROOT/'assets/kimodo/LICENSE.txt'],'https://github.com/nv-tlabs/kimodo')
    add('MASATAKA — CC0 contribution scope',[ROOT/'licenses/MASATAKA-CC0-NOTICE.txt',ROOT/'licenses/MASATAKA-CC0-scope.json',ROOT/'docs/CUSTOMIZATION_RIGHTS_JA.md',ROOT/'licenses/CC0-1.0.txt'],'https://creativecommons.org/publicdomain/zero/1.0/')
    seen=set()
    for dist in sorted(metadata.distributions(),key=lambda d:d.metadata.get('Name','').lower()):
        name=dist.metadata.get('Name','');key=name.lower().replace('_','-')
        if not name or key in seen or key=='motionbricks':continue
        seen.add(key)
        paths=[]
        for file in dist.files or []:
            if any(word in Path(str(file)).name.lower() for word in ('license','copying','notice')):
                path=Path(dist.locate_file(file))
                if path.is_file():paths.append(path)
        expression=dist.metadata.get('License-Expression','')
        if not expression:
            value=dist.metadata.get('License','')
            expression=value if value and len(value)<90 else 'See original notice'
        add(f'{name} {dist.version} — {expression}',paths)
    return tuple(entries)


@lru_cache(maxsize=128)
def notice_text(index):
    name,paths,_=catalog()[index]
    parts=[name]
    for path in paths:
        try:body=path.read_text(encoding='utf-8',errors='replace')
        except OSError as exc:body=str(exc)
        parts.append(f'\n--- {path.name} ---\n\n{body}')
    if not paths:parts.append('No standalone license file was supplied in the installed package. Consult its upstream distribution.')
    return '\n'.join(parts)


def draw_licenses(app,ui):
    title,component,website,close=LABELS.get(app.language,LABELS['en'])
    v=ui.get_main_viewport()
    ui.set_next_window_size(ui.ImVec2(min(960,v.size.x-40),min(850,v.size.y-60)),ui.Cond_.first_use_ever)
    visible,app.show_licenses=ui.begin(title+'###studio_licenses',app.show_licenses)
    try:
        if not visible:return
        ui.text_unformatted(CREDIT)
        ui.text_unformatted(PROFILE_URL)
        if ui.button('X (Twitter): @masatakaP###credit_profile'):webbrowser.open(PROFILE_URL)
        ui.separator()
        ui.begin_child('license_summary',ui.ImVec2(0,190),child_flags=ui.ChildFlags_.borders)
        ui.text_wrapped(SUMMARY.get(app.language,SUMMARY['en']))
        ui.separator()
        ui.text_wrapped(RIGHTS_NOTICE.get(app.language,RIGHTS_NOTICE['en']))
        ui.text_wrapped(CUSTOM_RIGHTS.get(app.language,CUSTOM_RIGHTS['en']))
        ui.separator()
        ui.text_wrapped(AUTODESK_ATTRIBUTION)
        ui.end_child()
        entries=catalog()
        _,app.license_index=ui.combo(component+'###license_component',app.license_index,[entry[0] for entry in entries])
        _,_,url=entries[app.license_index]
        if url and ui.button(website+'###license_website'):webbrowser.open(url)
        ui.begin_child('license_original',ui.ImVec2(0,-45),child_flags=ui.ChildFlags_.borders)
        ui.text_wrapped(notice_text(app.license_index))
        ui.end_child()
        if ui.button(close+'###license_close'):app.show_licenses=False
    finally:ui.end()

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
