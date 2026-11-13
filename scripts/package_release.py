"""Build a flat WorkBuddy ZIP and offline demo from the checked-in skill.

Python 3.10+, standard library only. No credentials or network requests.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'rd-compass'

def digest(content):
    return hashlib.sha256(content).hexdigest()

def zip_bytes(path, files):
    path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path,'w') as archive:
        for name,content in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info,content)

def build():
    original=(SKILL/'SKILL.md').read_text(encoding='utf-8-sig')
    version=re.search(r'version:\s*"([^"]+)"',original)[1]
    body=original.split('---',2)[2].lstrip()
    examples_zh=[
        '分析这批专利，先解释产品问题和各技术路线的发展，再提出有依据的研发方向。',
        '使用包内合成材料演示技术理解与机会探索，生成可离线打开的互动报告。',
        '按明确的目标比较两个方案，区分比较基准、研究优先与已验证性能。']
    examples_en=[
        'Explain the product context and technical approaches in this patent set, then identify conditional opportunities.',
        'Use the bundled synthetic material to generate an offline interactive research report.',
        'Compare two options under the stated goal, separating research priority from measured performance.']
    metadata={
        'name':'rd-compass','display_name':'研发罗盘','display_name_en':'R&D Compass',
        'description':'研发罗盘。解释产品技术现状与演进，探索有依据的研发机会，并按任务比较技术路线。',
        'description_zh':'先理解产品问题和现有技术，再推导研发机会；报告、阅读记录和证据同源更新。',
        'description_en':'Explain technical approaches and their evolution, explore conditional R&D opportunities, and compare options with traceable evidence.',
        'version':version,'author':'KrisMiao97'}
    header='---\n'+''.join(k+': '+json.dumps(v,ensure_ascii=False)+'\n' for k,v in metadata.items())
    for key,items in [('examples_zh',examples_zh),('examples_en',examples_en)]:
        header+=key+':\n'+''.join('- '+json.dumps(v,ensure_ascii=False)+'\n' for v in items)
    header+='---\n\n'
    adapter='''## WorkBuddy 使用入口

以本 SKILL.md 所在目录为技能根目录，按当前任务读取后续规则。脚本和参考路径相对技能根目录；把生成成果写到任务的可写目录，不覆盖技能原件或用户研究资料。先定位实际安装位置，不假定机器路径。

用户要求合成演示时，使用 assets/report-data.v2.example.json。Python 3.10+ 标准库命令示例（按实际安装位置替换输入和脚本路径，输出放任务目录）：

```sh
python scripts/render_report.py assets/report-data.v2.example.json --bundle TASK_OUTPUT
python scripts/render_report.py --check-bundle TASK_OUTPUT
```

包内 demo/index.html 是可直接打开的合成示例；查看它不需要 Python 或账号。没有命令工具时仍可按规则解释授权材料并交付文字，说明 HTML 未生成。真实研究不默认调用额外模型，不因安装获得数据库权限。

'''
    workbuddy_skill=header+body.replace('# 研发罗盘\n','# 研发罗盘\n\n'+adapter,1)
    readme=f'''# 研发罗盘 {version} · WorkBuddy 更新包

中文 / English

在 WorkBuddy 技能页选择“添加技能 → 上传技能”，选择本 ZIP。根目录 SKILL.md 的 name 保持 rd-compass，版本为 {version}。若客户端提示同名技能，请按界面提示处理；本包不自动改动已有研究数据或全局模型设置。

本次新增三种研究模式、现有路线与候选方向分离、事件类型、多点引用和阅读清单同步。默认报告解释技术及条件判断；只有任务需要时展开验证计划。

打开 demo/index.html 可直接查看合成示例，所有材料均虚构。生成新报告需要 Python 3.10+；真实检索需要宿主已授权来源。核心脚本与 GitHub 同版源一致，SKILL.md 增加双语发现字段和此宿主入口。

Upload this ZIP using Add skill → Upload skill. The root SKILL.md keeps the stable name rd-compass and version {version}. Follow the client prompt if an existing skill has the same name. Open demo/index.html for a fictional offline preview. Generating reports requires Python 3.10+; real research requires authorized sources. Core research instructions are primarily Chinese.

[官方上传说明 / Official upload guide](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)
[源代码 / Source](https://github.com/KrisMiao97/rd-compass)

本包已做解压、核心文件比对及渲染检查；不宣称已在 WorkBuddy 客户端完成导入。
'''
    files={p.relative_to(SKILL).as_posix():p.read_bytes() for p in SKILL.rglob('*')
           if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    core_hashes={name:digest(content) for name,content in files.items()}
    files['SKILL.md']=workbuddy_skill.encode('utf-8')
    files['README_WORKBUDDY.md']=readme.encode('utf-8')
    with tempfile.TemporaryDirectory() as temporary:
        subprocess.run([sys.executable,str(SKILL/'scripts/render_report.py'),
                        str(SKILL/'assets/report-data.v2.example.json'),'--bundle',temporary],check=True)
        subprocess.run([sys.executable,str(SKILL/'scripts/render_report.py'),'--check-bundle',temporary],check=True)
        report=(Path(temporary)/'report.html').read_bytes()
        files['demo/index.html']=report
        # The report embeds its own catalog and source data; the ZIP is standalone.
        demo_files={'index.html':report,'research-data.json':(Path(temporary)/'research-data.json').read_bytes()}
        (ROOT/'docs').mkdir(exist_ok=True)
        (ROOT/'docs/index.html').write_bytes(report)
        zip_bytes(ROOT/'docs/rd-compass-synthetic-demo.zip',demo_files)
    package=ROOT/'workbuddy'/f'rd-compass-workbuddy-{version}.zip'
    zip_bytes(package,files)
    manifest={'version':version,'layout':'SKILL.md at archive root','package':package.name,
              'sha256':digest(package.read_bytes()),'source_files_sha256':core_hashes,
              'package_files_sha256':{name:digest(content) for name,content in sorted(files.items())},
              'adapter_overrides':['SKILL.md'],'added':['README_WORKBUDDY.md','demo/index.html'],
              'validation_boundary':'Archive structure, core file equality and renderer execution; not a WorkBuddy client import.'}
    (ROOT/'workbuddy/package-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Built',package.name,'with',len(files),'files')

if __name__=='__main__':build()
