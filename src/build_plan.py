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
c.setTitle('소프트웨어랩 Term Project 계획서 - 머신러닝 PID와 MATLAB 검증')
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
y=para('<b>머신러닝과 수치 미적분을 이용한 Python PID 탐색 및 MATLAB 독립 검증</b>',M,y)
y-=13
y=section('2. 연계 강의 및 응용 내용',y)
y=para('<b>3강 적분·미분:</b> PID 적분항을 사다리꼴 누적 적분으로, 미분항을 후진 차분과 저역통과 필터로 계산한다. 응답 오차를 수치 적분해 ITAE 또는 ISE 비용을 구한다.',M,y)
y-=5
y=para('<b>7강 머신러닝 응용:</b> 입력 전달함수에서 PID 후보별 데이터를 생성하고 Gaussian Process(GP) 회귀로 성능을 학습한다. 예측과 불확실성으로 후보를 추천한 뒤 실제 시뮬레이션으로 재평가한다. MATLAB은 최종 이득을 받아 독립 계산한다.',M,y)
y-=5
y=para('<b>강의 연계의 범위:</b> GP는 프로젝트에서 선택한 확장 방법이다. 강의 원문이 없어 수업에서 GP를 직접 배웠다고 주장하지 않는다. Git과 AI 활용·검증 과정은 실제 이력으로 기록한다.',M,y)
y-=13
y=section('3. 동기 및 목표',y)
y=para('사용자가 전달함수를 직접 입력하고 Python에서 데이터 생성·ML 학습·PID 탐색을 수행한 뒤, 결과를 MATLAB에 적용해 확인한다. 수동 조절과 ML 추천 및 기존 수치 탐색을 비교하고, 모델의 예측 오차와 제어 성능을 구분해 평가한다.',M,y)
y-=5
y=para('기본 예제: G(s) = 10 exp(-0.1s) / [(s+1)(0.3s+1)(0.05s+1)(s²+0.4s+4)].<br/>직접 정한 무차원 실험 모델이며 특정 실제 장치의 식별 모델로 주장하지 않는다.',M,y,style=small)
y-=13
y=section('4. 구현 기능 목록',y)
y=table([
 ['구분','기능','구현 내용'],
 ['필수 F1','전달함수·PID 입력','분자·분모·지연, Kp·Ki·Kd, 목표값·dt·관측시간·ITAE/ISE 조절'],
 ['필수 F2','수치 계산과 지표','적분·차분·미분 필터, ITAE·ISE, 오버슈트·2% 정착시간·종료 오차'],
 ['필수 F3','데이터·GP 학습','실제 후보 응답 생성, GP fit/predict, 기대개선 기반 추천·재평가'],
 ['필수 F4','학습과 검증 분리','학습·탐색과 국소 홀드아웃 분리, 예측 MAE/RMSE/R²·데이터 저장'],
 ['필수 F5','MATLAB 검증·저장','최종 이득과 설정을 전달, 독립 응답 계산과 오차 비교, CSV·JSON 저장'],
 ['선택 S1','추가 실험','잡음·외란·포화 및 anti-windup 비교는 기본 기능 검증 후 확장'],
 ],[56,110,CW-166],y)
assert y>45,y
c.showPage()

y=title(2)
y=section('5. 성공 기준 및 평가 방법',y)
y=para('다음은 <b>평가 목표</b>이며 실제 측정값과 구분한다. 동일한 모델·시간 조건에서 수동 PID, ML 선택 PID, 대리모델을 학습하지 않는 Nelder-Mead 수치 탐색을 비교한다.',M,y)
y-=8
y=table([
 ['평가 대상','성공 목표','측정 방법'],
 ['수치 계산','적분·차분과 해석 가능한 기준 응답 일치','알려진 적분값·필터 차분식·1차 시스템 응답으로 확인한다. 지연 반올림과 dt 영향도 기록한다.'],
 ['ML 예측 검증','학습에 쓰지 않은 유효 표본 5개 이상과 오차 보고','최종 모델 동결 후 국소 홀드아웃의 log(1+J) MAE/RMSE/R²를 측정한다. 학습·최종 선택에 재사용하지 않는다.'],
 ['PID 탐색 비교','기본 ITAE 10% 이상 감소를 목표로 설정','같은 총 예산의 수동·ML·Nelder-Mead를 비교한다. ML 예산의 검증 비중과 오버슈트 등 상충관계도 보고한다.'],
 ['MATLAB 일치','출력·입력 최대 절대차 1e-7 미만','전달함수와 최종 PID를 받아 독립 계산한다. Python CSV는 계산 입력이 아닌 비교 기준으로 사용한다.'],
 ['안정성·한계','불안정·미정착 및 적용 범위 구분','이산 폐루프 고유값을 검사한다. 모델 변경 시 새로 학습하고 국소 검증을 전체 공간 정확도로 일반화하지 않는다.'],
 ],[88,155,CW-243],y)
y-=8
y=para('J_ITAE = ∫ t|r(t)-y(t)|dt,  J_ISE = ∫ [r(t)-y(t)]²dt (적분 구간: 0부터 T까지).<br/>시간 단위는 s. 유한 시간의 종료 오차는 엄밀한 정상상태 오차와 구분한다. 지연은 dt의 정수배로 근사하며 실제 적용 지연을 표시한다.',M,y,style=small)
y-=6
y=para('<b>ML 실측(2026. 11. 11.):</b> seed 42, 총 예산 180에서 ITAE 57.9983 → 5.4548(90.59% 감소). 같은 예산의 Nelder-Mead는 5.1593으로 더 낮았다. 국소 검증 24개의 로그 비용 R²=0.8295. MATLAB 최대 출력 차이 3.33e-15, 허용값 1e-7 통과. 근거: results/ml_benchmark.',M,y,style=small)
y-=15
y=section('6. 개발 환경 및 데이터',y)
y=para('<b>환경:</b> Python 3.12, NumPy·SciPy·Matplotlib·scikit-learn 1.7 이상. 실측은 scikit-learn 1.9.0, MATLAB R2026b Update 1을 사용했다. Base MATLAB expm 경로로 독립 계산하며 브라우저 버전은 Pyodide를 사용한다.',M,y)
y-=5
y=para('<b>데이터:</b> 전달함수·목표값·시간 조건을 고정하고 PID를 바꿔 만든 합성 데이터다. 학습/검증 표본과 예측 결과를 CSV로, 설정·학습 보고서를 JSON으로 저장한다. 측정 잡음·포화·외란·실물 장비는 현재 검증 범위에 없다.',M,y)
y-=5
y=para('<b>AI 활용:</b> Codex/ChatGPT로 코드와 문서 초안을 작성하고, 수식 대조·자동 검증·실행 화면 확인·MATLAB 독립 비교로 점검한다. 사용 도구, 적용 범위, 수정·검증 내역을 README에 기록한다.',M,y)
y-=15
y=section('7. 참고자료',y)
y=para('① 소프트웨어랩 3강 적분·미분, 7강 머신러닝: 연계 주제(세부 강의 원문 미제공)<br/>② 「00_TermProject_안내자료_통합본」, 2026학년도 2학기, 2·4~6쪽<br/>③ scikit-learn Gaussian Processes: GP 회귀와 예측 불확실성<br/><link href="https://scikit-learn.org/stable/modules/gaussian_process.html" color="#203E65">https://scikit-learn.org/stable/modules/gaussian_process.html</link><br/>④ SciPy cont2discrete 및 MathWorks expm 공식 문서(README에 링크)<br/>GP 문서 확인일: 2026. 11. 11. GP는 강의의 직접 실습 내용이라고 주장하지 않는다.',M,y,style=small)
assert y>45,y
c.save()
print(OUT/'TP계획서_학번_이름.pdf')
