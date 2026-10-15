#!/usr/bin/env python3
"""Prepare a seek-safe HyperFrames composition with per-frame subject occlusion."""
import argparse, json, math, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SKILL = Path(__file__).resolve().parents[1]

def run(*cmd):
    subprocess.run([str(v) for v in cmd], check=True)

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))

def raster(text, font, color):
    box = font.getbbox(text)
    im = Image.new('RGBA',(box[2]-box[0]+4,box[3]-box[1]+4))
    ImageDraw.Draw(im).text((2-box[0],2-box[1]),text,font=font,fill=color)
    return im

def split(im, axis, directory, index):
    """Stretch a 2px interior band, retaining the original glyph end shapes."""
    alpha = im.getchannel('A')
    n = im.width if axis == 'x' else im.height
    scores=[]
    for v in range(max(2,int(n*.25)), min(n-3,int(n*.7))):
        band = alpha.crop((v,0,v+1,im.height) if axis=='x' else (0,v,im.width,v+1))
        scores.append((sum(band.getdata()),v))
    cut=max(scores)[1]
    boxes = [(0,0,cut,im.height),(cut,0,cut+2,im.height),(cut+2,0,im.width,im.height)] if axis=='x' else [(0,0,im.width,cut),(0,cut,im.width,cut+2),(0,cut+2,im.width,im.height)]
    parts=[]
    for j,b in enumerate(boxes):
        p=im.crop(b); name=f'text-{index}-{j}.png'; p.save(directory/name)
        parts.append({'file':name,'w':p.width,'h':p.height,'x':b[0],'y':b[1]})
    return cut,parts

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',required=True,type=Path)
    p.add_argument('--project',required=True,type=Path)
    p.add_argument('--text',required=True,help='Rows separated by |')
    p.add_argument('--font',type=Path,default=SKILL/'assets/fonts/Anton-Regular.ttf')
    p.add_argument('--color',default='#B80609')
    p.add_argument('--offset',type=float,default=0)
    p.add_argument('--length',type=float)
    p.add_argument('--fps',type=float)
    p.add_argument('--width',type=int,help='Optional explicit resize, preserving aspect')
    p.add_argument('--x',type=float,default=.055)
    p.add_argument('--y',type=float,default=.04)
    p.add_argument('--font-size',type=int)
    p.add_argument('--stretch-x',type=float,default=.20,help='Extra width as canvas fraction')
    p.add_argument('--stretch-y',type=float,default=.52,help='Extra height as canvas fraction')
    p.add_argument('--mask-dir',type=Path,help='Exact numbered per-frame grayscale PNGs matching normalized source')
    a=p.parse_args()
    if a.offset<0 or (a.length is not None and a.length<=0): p.error('Invalid source range')
    if not 0<=a.x<1 or not 0<=a.y<1 or a.stretch_x<0 or a.stretch_y<0: p.error('Invalid geometry')
    a.project=a.project.resolve(); assets=a.project/'assets'; assets.mkdir(parents=True,exist_ok=True)
    if (a.project/'manifest.json').exists(): p.error('Refusing to overwrite a prepared project')
    info=probe(a.video); v=next(s for s in info['streams'] if s['codec_type']=='video')
    num,den=map(int,v['avg_frame_rate'].split('/')); fps=a.fps or num/den
    if not 1<=fps<=120: p.error('fps must be 1..120')
    source_duration=float(info['format']['duration'])
    if a.offset>=source_duration: p.error('offset outside source')
    length=min(a.length or source_duration-a.offset,source_duration-a.offset)
    filters=[f'fps={fps}']
    if a.width: filters.append(f'scale={a.width}:-2')
    filters.append('crop=trunc(iw/2)*2:trunc(ih/2)*2')
    run('ffmpeg','-hide_banner','-loglevel','error','-y','-ss',a.offset,'-i',a.video,'-t',length,'-vf',','.join(filters),'-c:v','libx264','-crf','18','-g',round(fps),'-keyint_min',round(fps),'-pix_fmt','yuv420p','-c:a','aac','-map','0:v:0','-map','0:a?','-movflags','+faststart',assets/'source.mp4')
    norm=probe(assets/'source.mp4'); v=next(s for s in norm['streams'] if s['codec_type']=='video')
    w,h=v['width'],v['height']; frames=int(v['nb_frames']); duration=frames/fps
    if duration<1.5: p.error('Need at least 1.5s for reveal/stretch/hold')
    mw=min(w,360); mh=round(h*mw/w)
    maskdir=a.mask_dir or a.project/'masks'
    if not a.mask_dir:
        cache=a.project/'swift-cache'; cache.mkdir(exist_ok=True)
        run('swift','-module-cache-path',cache,SKILL/'scripts/video_masks.swift',assets/'source.mp4',maskdir,mw,mh)
    files=sorted(maskdir.glob('*.png'))
    if len(files)!=frames: p.error(f'Mask count {len(files)} != source frames {frames}')
    if a.mask_dir:
        mw,mh=w,h
        if any(Image.open(f).size!=(w,h) for f in files): p.error('Supplied masks must match normalized dimensions')
    # Paged alpha atlases avoid browser texture size limits for long clips.
    cols=8; rows=max(1,min(8,8192//mh)); perpage=cols*rows; pages=[]
    for first in range(0,frames,perpage):
        atlas=Image.new('RGBA',(mw*cols,mh*rows))
        for j,path in enumerate(files[first:first+perpage]):
            mask=Image.open(path).convert('L').filter(ImageFilter.GaussianBlur(.35))
            tile=Image.new('RGBA',(mw,mh),(255,255,255,0)); tile.putalpha(mask)
            atlas.paste(tile,((j%cols)*mw,(j//cols)*mh))
        name=f'mask-atlas-{len(pages)}.png'; atlas.save(assets/name); pages.append(name)
    shutil.copyfile(SKILL/'assets/gsap.min.js',assets/'gsap.min.js')
    font=ImageFont.truetype(str(a.font),a.font_size or round(w*.17))
    texts=[s.strip() for s in a.text.split('|') if s.strip()]
    if not texts: p.error('Empty text')
    if a.font.name=='Anton-Regular.ttf' and any(ord(c)>127 for c in ''.join(texts)):
        p.error('Anton is Latin-only; supply --font covering the requested characters')
    # Reserve room for the horizontal extension without crushing the font.
    images=[raster(t,font,a.color) for t in texts]
    max_width=w*(1-a.x-.035)-(w*a.stretch_x if len(texts)>1 else 0)
    factor=min(1,max_width/max(i.width for i in images))
    images=[im.resize((max(8,round(im.width*factor)),max(8,round(im.height*factor))),Image.Resampling.LANCZOS) for im in images]
    markup=[]; tweens=[]; y=round(a.y*h); layout=[]
    span=min(duration,3.5)/3.5
    for i,im in enumerate(images):
        axis='y' if i==len(images)-1 else 'x'; cut,parts=split(im,axis,assets,i)
        extra=round((a.stretch_y*h if axis=='y' else a.stretch_x*w))
        if axis=='y': extra=min(extra,max(0,h*.94-y-im.height))
        markup.append(f'<div id="row-{i}" style="position:absolute;left:{a.x*w}px;top:{y}px;width:{im.width+(extra if axis=="x" else 0)}px;height:{im.height+(extra if axis=="y" else 0)}px">')
        for j,part in enumerate(parts):
            markup.append(f'<img id="piece-{i}-{j}" alt="" src="assets/{part["file"]}" style="position:absolute;left:{part["x"]}px;top:{part["y"]}px;width:{part["w"]}px;height:{part["h"]}px;transform-origin:0 0">')
        markup.append('</div>')
        reveal=(.12+i*.12)*span; stretch=(.75+i*.14)*span
        tweens += [f'tl.fromTo("#row-{i}",{{opacity:0,y:18}},{{opacity:1,y:0,duration:{.23*span},ease:"power3.out"}},{reveal});',f'tl.to("#piece-{i}-1",{{{"scaleX" if axis=="x" else "scaleY"}:{(2+extra)/2},duration:{.72*span},ease:"power3.inOut"}},{stretch});',f'tl.to("#piece-{i}-2",{{{axis}:{extra},duration:{.72*span},ease:"power3.inOut"}},{stretch});']
        layout.append({'text':texts[i],'axis':axis,'cut':cut,'extra':extra,'y':y,'width':im.width,'height':im.height})
        y+=im.height+round(h*.009)
    for n in range(frames):
        page=n//perpage; cell=n%perpage
        # The duplicate foreground video and the base share exact media timing.
        props={'maskImage':f'url("assets/{pages[page]}")','webkitMaskImage':f'url("assets/{pages[page]}")','maskPosition':f'{-(cell%cols)*w}px {-math.floor(cell/cols)*h}px','webkitMaskPosition':f'{-(cell%cols)*w}px {-math.floor(cell/cols)*h}px'}
        tweens.append(f'tl.set("#foreground",{json.dumps(props)},{n/fps:.8f});')
    audio='data-has-audio="true"' if any(s['codec_type']=='audio' for s in norm['streams']) else 'muted'
    html='''<!doctype html><html><head><meta charset="UTF-8"><script src="assets/gsap.min.js"></script><style>
html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#000}
#root{position:relative;width:100%;height:100%;overflow:hidden}
video,.full{position:absolute;inset:0;width:100%;height:100%;object-fit:fill}
#base{z-index:0}#letters{z-index:1}#foreground{z-index:2;mask-repeat:no-repeat;-webkit-mask-repeat:no-repeat;mask-mode:alpha;mask-size:COLSWpx ROWSHpx;-webkit-mask-size:COLSWpx ROWSHpx}
</style></head><body><div id="root" data-composition-id="text-behind-subject" data-width="WIDTH" data-height="HEIGHT" data-duration="DURATION" data-fps="FPS">
<video id="base" class="clip" src="assets/source.mp4" data-start="0" data-duration="DURATION" data-track-index="0" AUDIO playsinline></video>
<div id="letters" class="clip full" data-start="0" data-duration="DURATION" data-track-index="1">MARKUP</div>
<div id="foreground" class="full"><video id="person" class="clip" src="assets/source.mp4" data-start="0" data-duration="DURATION" data-track-index="2" muted playsinline></video></div>
</div><script>const tl=gsap.timeline({paused:true});TWEENS
window.__timelines["text-behind-subject"]=tl;</script></body></html>'''
    for key,value in {'COLSW':cols*w,'ROWSH':rows*h,'WIDTH':w,'HEIGHT':h,'DURATION':duration,'FPS':fps,'AUDIO':audio,'MARKUP':''.join(markup),'TWEENS':'\n'.join(tweens)}.items(): html=html.replace(key,str(value))
    (a.project/'index.html').write_text(html)
    manifest={'source':str(a.video.resolve()),'offset':a.offset,'width':w,'height':h,'fps':fps,'frames':frames,'duration':duration,'color':a.color,'text':texts,'font':str(a.font),'mask_frames':len(files),'mask_method':'provided' if a.mask_dir else 'Apple Vision per-frame person segmentation (all people)','layout':layout,'audio':audio,'atlas_pages':len(pages)}
    (a.project/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
    print(json.dumps({'project':str(a.project),'frames':frames,'duration':duration,'color':a.color}))

if __name__=='__main__': main()
