from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parents[1]
OUT.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Malgun', r'C:\Windows\Fonts\malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold', r'C:\Windows\Fonts\malgunbd.ttf'))
pdfmetrics.registerFontFamily('Malgun', normal='Malgun', bold='MalgunBold')
NAVY = colors.HexColor('#203E65')
INK = colors.HexColor('#172536')
GRAY = colors.HexColor('#586574')
LIGHT = colors.HexColor('#EAF0F5')
W,H = A4
M = 46
CW = W - 2*M
c = canvas.Canvas(str(OUT/'TP계획서_학번_이름.pdf'), pagesize=A4)
c.setTitle('소프트웨어랩 Term Project 계획서 - Python PID 최적화와 MATLAB 검증')
c.setAuthor('학번·이름 작성 필요')
sty = ParagraphStyle('body', fontName='Malgun', fontSize=9.6, leading=15, textColor=INK, wordWrap='CJK')
small = ParagraphStyle('small', parent=sty, fontSize=8.2, leading=12.4)
cell = ParagraphStyle('cell', parent=sty, fontSize=8.5, leading=12.6)
head = ParagraphStyle('head', parent=sty, fontName='MalgunBold', fontSize=9.2, leading=13, textColor=colors.white)

def para(s,x,y,w=CW,style=sty):
    p=Paragraph(s,style)
    _,hh=p.wrap(w,1000)
    p.drawOn(c,x,y-hh)
    return y-hh

def title(n):
    c.setFillColor(NAVY)
    c.setFont('MalgunBold',18)
    c.drawString(M,H-52,'소프트웨어랩 Term Project 계획서')
    c.setFont('Malgun',8.4)
    c.setFillColor(GRAY)
    c.drawString(M,H-70,'결과물 zip에 포함하여 제출(2026. 12. 13.(일) 23:59) · A4 1~2쪽')
    c.setStrokeColor(NAVY)
    c.setLineWidth(1)
    c.line(M,H-81,W-M,H-81)
    c.setFont('Malgun',8)
    c.drawRightString(W-M,25,f'{n} / 2')
    c.drawString(M,25,'2026. 11. 11. 작성 · 계획서 목표와 실험 결과를 구분하여 관리')
    return H-94

def section(s,y):
    c.setFillColor(NAVY)
    c.setFont('MalgunBold',11.5)
    c.drawString(M,y-12,s)
    return y-24

def table(rows,widths,y,header=True,identity=False):
    cells=[[Paragraph(str(v),head if (header and i==0) else cell) for v in row] for i,row in enumerate(rows)]
    t=Table(cells,colWidths=widths,hAlign='LEFT')
    cmds=[('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#A7B4C0')),
          ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
          ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]
    if header: cmds.append(('BACKGROUND',(0,0),(-1,0),NAVY))
    if identity:
        cmds += [('SPAN',(1,1),(3,1)),('BACKGROUND',(0,0),(0,1),LIGHT),('BACKGROUND',(2,0),(2,0),LIGHT)]
    t.setStyle(TableStyle(cmds))
    _,hh=t.wrap(CW,1000)
    t.drawOn(c,M,y-hh)
    return y-hh

y=title(1)
y=table([['학번','작성 필요','이름','작성 필요'],['GitHub 저장소 URL','<link href="https://github.com/samueli02/pid-optimization-python-matlab" color="#203E65">https://github.com/samueli02/pid-optimization-python-matlab</link>','','']], [99,153,65,CW-317],y,False,True)
y-=15
y=section('1. 주제명',y)
y=para('<b>수치 미분·적분으로 구현한 Python PID 최적화와 MATLAB 독립 검증</b>',M,y)
y-=13
y=section('2. 연계 강의 및 응용 내용',y)
y=para('<b>3강 적분·미분(핵심):</b> PID의 적분항을 사다리꼴 누적 적분으로, 미분항을 오차의 후진 차분과 저역통과 필터로 계산한다. 응답 오차를 다시 수치 적분하여 ITAE 또는 ISE 목적함수를 구한다.',M,y)
y-=5
y=para('<b>강의 실습에서 확장하는 부분:</b> 수치 계산을 지연이 있는 5차 시스템의 폐루프 제어에 적용하고, PID 세 이득을 탐색해 수동 조절과 비교한다. Python이 시뮬레이션과 최적화를 수행하며 MATLAB은 확정된 이득을 받아 같은 설정을 독립적으로 재계산한다.',M,y)
y-=5
y=para('<b>12~14강 Git·바이브코딩(보조):</b> 기능별 개발 이력과 AI 활용·검증 과정을 남기며, 입력 설정과 결과 파일로 실험을 재현한다.',M,y)
y-=13
y=section('3. 동기 및 목표',y)
y=para('PID 값을 감으로 바꾸면 빠른 응답, 작은 오버슈트, 작은 오차 사이의 관계를 비교하기 어렵다. 사용자가 이득과 전달함수를 조절하며 응답을 확인하고, 선택한 오차 기준을 최소화한 결과와 비교하는 학습용 프로그램을 만든다.',M,y)
y-=5
y=para('기본 예제: G(s) = 10 exp(-0.1s) / [(s+1)(0.3s+1)(0.05s+1)(s²+0.4s+4)].<br/>직접 정한 무차원 실험 모델이며 특정 실제 장치의 식별 모델로 주장하지 않는다.',M,y,style=small)
y-=13
y=section('4. 구현 기능 목록',y)
y=table([
 ['구분','기능','구현 내용'],
 ['필수 F1','수동 PID 조절','Kp·Ki·Kd 슬라이더와 숫자 입력, 목표값·출력·제어입력 그래프'],
 ['필수 F2','수치 계산과 지표','적분·차분·미분 필터, ITAE·ISE, 오버슈트·2% 정착시간·종료 오차'],
 ['필수 F3','Python 자동 최적화','이득 범위·탐색 예산·난수 시드 지정, 수동/최적화 응답 겹쳐 비교'],
 ['필수 F4','모델·목적함수 변경','전달함수 계수·감쇠·시간지연, ITAE/ISE, dt·측정시간 조절'],
 ['필수 F5','MATLAB 검증·저장','최종 이득과 설정을 전달, 독립 응답 계산과 오차 비교, CSV·JSON 저장'],
 ['선택 S1','추가 실험','잡음·외란·포화 및 anti-windup 비교는 기본 기능 검증 후 확장'],
 ],[56,110,CW-166],y)
assert y>45,y
c.showPage()

y=title(2)
y=section('5. 성공 기준 및 평가 방법',y)
y=para('아래 수치는 개발 전 설정한 <b>성공 목표</b>이다. 측정값과 달성 여부는 실제 실행 결과로 기록한다. 동일한 플랜트·시뮬레이션 조건에서 수동 기준값과 최적화 결과를 비교한다.',M,y)
y-=8
y=table([
 ['평가 대상','성공 목표','측정 방법'],
 ['수치 계산 정확도','적분·미분 구현의 기준값 일치, dt 감소 시 오차 감소','상수·다항식 등 해석값이 있는 입력으로 검증한다. 필터를 적용한 미분은 해당 이산 차분식과 비교한다.'],
 ['PID 최적화','기본 예제 ITAE 10% 이상 감소를 목표로 설정','개선율 = 100×(J수동 - J최적)/J수동. 고정 seed·범위·예산을 저장한다. ISE 최적화와도 비교한다.'],
 ['Python/MATLAB 일치','최대 출력 절대 차이 1e-6 이하','동일 dt·ZOH·지연 샘플 수·PID 갱신 순서에서 두 출력 배열을 비교한다. 실행 불가 시 미검증으로 남긴다.'],
 ['안정성·한계 분석','불안정·미정착 사례를 정상 결과와 구분','이산 폐루프의 고유값을 검사한다. 2% 대역 내에 유지되지 않으면 정착시간을 미정착으로 표시한다.'],
 ['파라미터 영향','기본 비교 외 2종 이상 조건 변화 실험','지연·감쇠·dt를 하나씩 바꾸고 ITAE·ISE·오버슈트·정착시간·종료 오차를 비교한다.'],
 ],[88,155,CW-243],y)
y-=8
y=para('J_ITAE = ∫ t|r(t)-y(t)|dt,  J_ISE = ∫ [r(t)-y(t)]²dt (적분 구간: 0부터 T까지).<br/>시간 단위는 s. 유한 시간의 종료 오차는 엄밀한 정상상태 오차와 구분한다. 지연은 dt의 정수배로 근사하며 실제 적용 지연을 표시한다.',M,y,style=small)
y-=6
y=para('<b>현재 실측(2026. 11. 11.):</b> seed 42, 평가 예산 180, dt 0.01s, T 30s에서 ITAE 57.9983 → 5.1593(91.10% 감소). 오버슈트는 0 → 9.98%로 증가했다. MATLAB 최대 출력 차이는 4.44e-15로 검증 코드의 허용값 1e-7을 통과했다.',M,y,style=small)
y-=15
y=section('6. 개발 환경 및 데이터',y)
y=para('<b>환경:</b> Windows 11, Python 3.12.13, NumPy 2.4.6, SciPy 1.18.0, Matplotlib 3.10.9, 웹 브라우저. MATLAB R2026b Update 1에서 제어가능 표준형과 증강 행렬 expm으로 ZOH를 독립 계산했다. Control System Toolbox 없이 실행 가능하다.',M,y)
y-=5
y=para('<b>데이터:</b> 직접 정의한 전달함수·계단 목표값·PID 초기값을 JSON 샘플로 제공한다. 외부 실측 데이터는 사용하지 않는다. 결과는 시뮬레이션 생성 데이터이며 설정·시간·입출력·지표를 함께 저장한다.',M,y)
y-=5
y=para('<b>AI 활용:</b> Codex/ChatGPT로 코드와 문서 초안을 작성하고, 수식 대조·자동 검증·실행 화면 확인·MATLAB 독립 비교로 점검한다. 사용 도구, 적용 범위, 수정·검증 내역을 README에 기록한다.',M,y)
y-=15
y=section('7. 참고자료',y)
y=para('① 소프트웨어랩 3강 적분·미분, 12~14강 Git·바이브코딩 강의자료<br/>② 「00_TermProject_안내자료_통합본」, 2026학년도 2학기, 2·4~6쪽<br/>③ SciPy 공식 문서, scipy.signal.cont2discrete (ZOH 이산화)<br/><link href="https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.cont2discrete.html" color="#203E65">https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.cont2discrete.html</link><br/>④ MathWorks 공식 문서, expm (행렬 지수함수)<br/><link href="https://www.mathworks.com/help/matlab/ref/expm.html" color="#203E65">https://www.mathworks.com/help/matlab/ref/expm.html</link><br/>공식 문서 확인일: 2026. 11. 11. 강의자료의 세부 코드와 인용 위치는 제출 전 대조한다.',M,y,style=small)
assert y>45,y
c.save()
print(OUT/'TP계획서_학번_이름.pdf')
