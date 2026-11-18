"""Simple upload-free batch workflow, with optional advanced controls."""
import hashlib
import zipfile
from pathlib import PurePosixPath
import pandas as pd
import streamlit as st
from core.batch import analyze_batch, batch_csv, zip_inputs
from core.detector import Config
from core.dataset import bundled_files
from core.comparison import comparison_images, reference_image


@st.cache_data(show_spinner=False, max_entries=2)
def load_bundled(group):
    return bundled_files(group)


@st.cache_data(show_spinner=False, max_entries=8)
def comparison(data, config, expected_count, expected_sha):
    return comparison_images(data, config, expected_count, expected_sha)


def preview(files, group):
    images = [(n,d) for n,d in files if n.endswith('.png')]
    if not images:
        return
    page = st.selectbox('사진 페이지', range(1, (len(images)+11)//12+1), key=f'preview_{group}')
    shown = images[(page-1)*12:page*12]
    st.image([d for _,d in shown], caption=[PurePosixPath(n).name for n,_ in shown], width=150)


def show_comparison(rows, files, cfg, fingerprint):
    image_data = dict(files)
    choices = [i for i,r in enumerate(rows) if r.get('image_name') in image_data]
    if not choices:
        return
    st.subheader('② 사진으로 결과 확인')
    chosen = st.selectbox('확인할 사진', choices,
        format_func=lambda i: PurePosixPath(rows[i]['image_name']).name + (' · 주석 오류' if rows[i]['status']=='error' else ''),
        key=f'comparison_{fingerprint[:16]}')
    row = rows[chosen]
    position = choices.index(chosen)
    previous, following = st.columns(2)
    def move(offset):
        st.session_state[f'comparison_{fingerprint[:16]}'] = choices[position+offset]
    previous.button('← 이전 사진', disabled=position==0, on_click=move, args=(-1,))
    following.button('다음 사진 →', disabled=position==len(choices)-1, on_click=move, args=(1,))
    st.caption(f'{position+1} / {len(choices)}장 · 사진 목록에서 고르거나 이전·다음 버튼으로 이동하세요.')
    data = image_data[row['image_name']]
    if row['status'] != 'ok':
        st.warning(f"이 사진은 정답 검증을 하지 못했습니다: {row['message']}")
        try:
            from core.detector import read_image
            st.image(read_image(data), caption='분석 전 · 원본', use_container_width=True)
        except (ValueError, OSError):
            st.error('사진을 열 수 없습니다.')
        return
    before, after = comparison(data, cfg, row['auto_count'], row['image_sha256'])
    a,b,c=st.columns(3)
    a.metric('프로그램이 센 수', f"{row['auto_count']}개", help='프로그램이 세포라고 판단한 초록색 원의 수입니다. 실제 세포가 아닌 것이 포함되거나 세포를 놓칠 수 있습니다.')
    b.metric('비교 기준 수', f"{row['ground_truth_count']}개", help='정답 역할을 하는 수입니다. CIDACC 제작자가 미리 표시한 개별 세포 주석을 셉니다. 지금 사용자가 직접 센 수가 아닙니다. 뭉침 주석은 제외합니다.')
    c.metric('두 수의 차이', f"{row['absolute_error']}개", help='두 개수의 차이입니다. 틀린 위치의 개수나 정확도를 뜻하지 않습니다.')
    difference = row['auto_count']-row['ground_truth_count']
    meaning = f"{abs(difference)}개 {'많이' if difference>0 else '적게'} 셌습니다." if difference else '두 개수가 같습니다.'
    st.write(f"이 사진에서 프로그램은 **{row['auto_count']}개**, 데이터 제작자가 미리 표시한 기준은 **{row['ground_truth_count']}개**입니다. {meaning}")
    st.caption('개수가 같아도 위치가 맞는지는 별도 확인이 필요합니다. 개수 차이가 1개라고 틀린 위치가 딱 1곳이라는 뜻은 아닙니다.')
    st.info('🟢 초록색 원 = 프로그램이 세포로 판단해 센 곳입니다. 틀릴 수도 있습니다.\n\n🟠 주황색 원 = 크기나 모양 때문에 확신하지 못한 곳입니다. 위의 개수에 넣지 않았습니다. 세포가 없다는 뜻은 아닙니다.')
    st.markdown('''<style>
    .st-key-reference_panel {background:#edf5ff; border:2px solid #2878ce; border-radius:14px; padding:18px;}
    .st-key-reference_panel button {background:#1763b4 !important; color:white !important;
      border:2px solid #1763b4 !important; font-size:1.1rem; min-height:54px;}
    .st-key-reference_panel button:hover {background:#104a89 !important;}
    </style>''', unsafe_allow_html=True)
    st.session_state.setdefault('reference_visible',False)
    def toggle_reference():
        st.session_state['reference_visible']=not st.session_state['reference_visible']
    with st.container(border=True,key='reference_panel'):
        st.subheader('🔵 제작자가 표시한 정답 위치 보기')
        st.write(f"**기준 {row['ground_truth_count']}개가 어디에 있는지 궁금하다면 아래 버튼을 누르세요.** 왼쪽 사진에 파란 네모로 표시합니다.")
        visible=st.session_state['reference_visible']
        st.button('✓ 파란 네모 표시 중 · 끄고 원본 보기' if visible else '🔵 정답 위치 보기 · 파란 네모 켜기',
                  on_click=toggle_reference,key='reference_toggle_button',use_container_width=True)
    show_reference=st.session_state['reference_visible']
    if show_reference:
        annotation = image_data.get(row['annotation_name'])
        if annotation is None:
            raise ValueError('정답 위치를 표시할 TXT가 없습니다.')
        before=reference_image(data,annotation,row['ground_truth_count'])
    left,right=st.columns(2)
    left.image(before, caption='비교 기준 · 제작자의 정답 위치 (파란 네모)' if show_reference else '분석 전 · 원본 사진', use_container_width=True)
    right.image(after, caption='분석 후 · 프로그램이 표시한 위치', use_container_width=True)
    with st.expander('처음이라면: 결과를 어떻게 읽나요?'):
        st.write('1. 오른쪽 초록색 원이 실제 세포 위에 있는지 보세요. 배경이나 격자선에 표시되면 잘못 센 후보입니다.')
        st.write('2. 세포가 보이는데 초록색 원이 없으면 놓친 후보일 수 있습니다. 주황색 원은 개수에 포함되지 않습니다.')
        st.write('3. 위의 정답 위치 보기를 켜면 왼쪽 파란 네모와 오른쪽 검출 위치를 비교할 수 있습니다.')
        st.write('기준 수는 공개 데이터의 주석을 이용한 비교 기준이며 주석 자체의 오류 가능성도 있습니다. 현재 도구는 OpenCV 이미지 처리 방식이고, 학습형 AI가 아닙니다.')
    st.download_button('이 분석 사진 저장', after, f"{PurePosixPath(row['image_name']).stem}_detected.png", 'image/png')


def render_batch():
    st.subheader('사진 속 세포, 한 번에 확인하세요')
    st.write('사진 464장이 준비되어 있습니다. 분석 시작을 누르면 원본과 검출 표시를 비교할 수 있습니다.')
    st.caption('사용 순서: ① 분석 시작 → ② 사진을 골라 표시와 개수 확인 → ③ 사진 또는 전체 결과 저장. 설정은 처음에는 그대로 두세요.')
    run_slot=st.container()
    files=[]
    cfg=Config()
    try:
        with st.expander('다른 사진 선택 · 분석 설정 (선택 사항)'):
            source=st.radio('데이터 준비 방법', ['준비된 CIDACC 전체 데이터','이미지와 TXT 함께 업로드','CIDACC ZIP 업로드'])
            if source=='준비된 CIDACC 전체 데이터':
                group=st.radio('사진 종류',['개별 세포 · 464장','뭉친 세포 · 164장'])
                if group=='뭉친 세포 · 164장':
                    cluster_view=True
                    files=load_bundled('clusters')
                else:
                    cluster_view=False
                    files=load_bundled('distinct')
                    selection=st.radio('분석 범위',['전체 464장','일부 사진 선택'])
                    if selection=='일부 사진 선택':
                        names=[n for n,_ in files if n.endswith('.png')]
                        selected=st.multiselect('분석할 사진',names,default=names[:10])
                        stems={PurePosixPath(n).stem for n in selected}
                        files=[(n,d) for n,d in files if PurePosixPath(n).stem in stems]
            elif source=='CIDACC ZIP 업로드':
                cluster_view=False
                up=st.file_uploader('CIDACC ZIP',type=['zip'])
                if up:
                    files=zip_inputs(up.getvalue())
                    names=[n for n,_ in files if '/images/' in n and n.lower().endswith('.png')]
                    selected=st.multiselect('분석할 사진 (최대 464장)',sorted(names),default=sorted(names),max_selections=464)
                    stems={PurePosixPath(n).stem.casefold() for n in selected}
                    files=[(n,d) for n,d in files if n in selected or (n.lower().endswith('.txt') and PurePosixPath(n).stem.casefold() in stems)]
            else:
                cluster_view=False
                st.write('distinct 이미지와 같은 이름의 정답 TXT를 함께 선택하세요.')
                uploads=st.file_uploader('PNG 사진과 bbs TXT',type=['png','txt'],accept_multiple_files=True)
                files=[(u.name,u.getvalue()) for u in uploads]
            if not cluster_view:
                mode=st.selectbox('검출 방식',['auto','gray','green'])
                sensitivity=st.slider('민감도',0,100,50,key='batch_sensitivity')
                a,b=st.columns(2)
                minimum=a.number_input('최소 면적(px²)',min_value=1,value=18,key='batch_min')
                maximum=b.number_input('최대 면적(px²)',min_value=1,value=2200,key='batch_max')
                cfg=Config(mode=mode,sensitivity=sensitivity,min_area=minimum,max_area=maximum)
        if cluster_view:
            st.warning('뭉친 세포 사진은 개별 세포 정답 개수를 확인하기 어려워 사진만 볼 수 있습니다.')
            preview(files,'clusters')
            return
        count=sum(PurePosixPath(n).suffix.lower() in ('.png','.jpg','.jpeg') for n,_ in files)
        fingerprint=hashlib.sha256(repr(([(n,hashlib.sha256(d).hexdigest()) for n,d in files],cfg)).encode()).hexdigest()
        if run_slot.button(f'① 분석 시작 · {count}장',disabled=not files,type='primary',use_container_width=True):
            with st.spinner('사진을 분석하고 있습니다…'):
                bar=st.progress(0)
                st.session_state['batch_result']=(fingerprint,analyze_batch(files,cfg,progress=lambda done,total:bar.progress(done/total,text=f'{done} / {total}장 처리')))
                bar.empty()
        saved=st.session_state.get('batch_result')
        if saved and saved[0]==fingerprint:
            rows=saved[1]
            good=[r for r in rows if r['status']=='ok']
            st.success(f"분석 완료 · 정상 {len(good)}장 / 확인이 필요한 파일 {len(rows)-len(good)}건")
            show_comparison(rows,files,cfg,fingerprint)
            st.subheader('③ 전체 결과 저장')
            st.download_button('전체 결과 CSV 다운로드',batch_csv(rows),'cidacc_batch_validation.csv','text/csv')
            with st.expander('전체 결과표 · 오류 내용 보기'):
                if good:
                    st.metric('평균 개수 차이(MAE)',round(sum(r['absolute_error'] for r in good)/len(good),3))
                table=pd.DataFrame(rows)
                st.dataframe(table.reindex(columns=['image_name','auto_count','ground_truth_count','absolute_error','percentage_error','status','message']).rename(columns={
                    'image_name':'사진','auto_count':'자동 계수','ground_truth_count':'정답 개수','absolute_error':'절대오차','percentage_error':'오차율(%)','status':'상태','message':'안내'}),hide_index=True)
                st.caption('정답이 없거나 잘못된 사진은 오차 계산에서 제외합니다. 정답이 0개면 백분율오차를 계산하지 않습니다.')
        elif saved:
            st.info('사진 또는 설정이 바뀌었습니다. 분석 시작을 다시 눌러 주세요.')
        else:
            st.caption('처음에는 설정을 바꾸지 않고 분석 시작을 눌러 보세요.')
        with st.expander('이 앱과 데이터 안내'):
            st.write('OpenCV 이미지 처리 도구이며 학습형 AI가 아닙니다. 격자선을 세포로 잘못 셀 수 있어 분석 후 사진을 확인하세요.')
            st.caption('출처: Pistolas et al. (2024), [CIDACC](https://doi.org/10.5281/zenodo.13219972), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). 사진·TXT는 원본 그대로 포함했습니다.')
            st.caption('클래스 0은 개별 세포, 1은 뭉침(계수 제외)입니다. 원본 335.txt, 515.txt는 비어 있어 오류로 안내합니다.')
    except (ValueError,OSError,zipfile.BadZipFile,RuntimeError) as exc:
        st.error(f'분석할 수 없습니다: {exc}')
