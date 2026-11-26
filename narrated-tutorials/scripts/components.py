"""Small reusable card components shared by storyboard and final rendering."""

def header(draw,scene,style,font,wrap):
    draw.rectangle((0,0,1920,14),fill=style['accent'])
    draw.text((80,42),scene.get('kind','步骤讲解 / Step guide'),font=font(25),fill='#53657b')
    title=wrap(scene['title'],font(52),1750)
    if len(title)>2:raise ValueError('Scene title too long: '+scene['title'])
    for i,line in enumerate(title):draw.text((80,90+i*65),line,font=font(52),fill=style['text'])

def steps(draw,points,style,font,wrap):
    y=268
    for i,point in enumerate(points,1):
        lines=wrap(point,font(39),1550)
        if y+58*len(lines)>(825 if style.get('caption_space') else 934):raise ValueError('Too much scene text; split into more scenes')
        draw.rounded_rectangle((80,y,140,y+58),radius=13,fill='#e2eafe')
        draw.text((110,y+29),str(i),anchor='mm',font=font(31),fill=style['accent'])
        for j,line in enumerate(lines):draw.text((175,y+j*58),line,font=font(39),fill=style['text'])
        y+=len(lines)*58+30

def flow(draw,labels,style,font,wrap):
    if not isinstance(labels,list) or not 2<=len(labels)<=4 or not all(isinstance(x,str) and x.strip() for x in labels):
        raise ValueError('flow needs 2–4 nonempty text labels')
    width=(1720-44*(len(labels)-1))/len(labels);top=340;height=255
    for i,label in enumerate(labels):
        x=100+i*(width+44);lines=wrap(label,font(36),width-40)
        if len(lines)>4:raise ValueError('Flow label too long; shorten it or split the diagram')
        draw.rounded_rectangle((x,top,x+width,top+height),radius=23,fill='white',outline=style['accent'],width=3)
        draw.ellipse((x+20,top+18,x+66,top+64),fill=style['accent'])
        draw.text((x+43,top+41),str(i+1),anchor='mm',font=font(27),fill='white')
        for j,line in enumerate(lines):draw.text((x+width/2,top+143+(j-(len(lines)-1)/2)*47),line,anchor='mm',font=font(36),fill=style['text'])
        if i<len(labels)-1:
            a=x+width+6;b=x+width+38;y=top+height/2
            draw.line((a,y,b,y),fill=style['accent'],width=4)
            draw.polygon(((b,y),(b-12,y-9),(b-12,y+9)),fill=style['accent'])

def footer(draw,scene,style,font,wrap):
    text=scene.get('footer','AI 合成旁白 · Synthetic narration')
    for i,line in enumerate(wrap(text,font(24),1750)[:2]):draw.text((80,(850 if style.get('caption_space') else 975)+i*32),line,font=font(24),fill='#53657b')
