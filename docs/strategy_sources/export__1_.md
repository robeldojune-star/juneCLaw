# Extracted source: export__1_.docx

> 원본 Word 파일에서 추출한 전략 리서치 텍스트입니다. 원본 docx는 Git ignore 대상이며, 이 Markdown은 전략 등록/분석을 위한 참조본입니다.

코스피 200 종목의 당일 양봉 마감 예측을 위해 가격 변동성, 수급 지표, 90일 시계열 패턴을 종합한 알고리즘 매수 스코어링 시스템을 제안합니다. 이 시스템은 고빈도 데이터 분석과 머신러닝 모델을 결합하여 시장의 비효율성을 포착하고 최적의 진입 시점을 결정하는 데 중점을 둡니다.가격 변동성 및 시장 리스크 분석일중 변동성 패턴 및 VKOSPI 활용코스피 200 시장에서 변동성은 주로 개장 및 폐장 시간대에 집중되며, 정보 유입과 거래 활동이 주요 원인으로 작용합니다. 특히 2026년 3월 초 전쟁 여파로 코스피200 변동성 지수{{1}}(VKOSPI)가 80.37까지 급등한 사례에서 볼 수 있듯이, 변동성 지수는 시장의 공포와 반등 가능성을 예측하는 중요
한 지표입니다. 알고리즘은 VKOSPI와 지수 간의 음
의 상관관계를 이용하여 과매도 구간에서의 기술적 반등{{2}} 가능성을 점수에 반영해야 합니다.가격 발견 효율성 및 변동성 곡률옵션 가격에 내재된 변동성 곡률{{3}}과 왜도 프리미엄은 기초 자산의 가격 방향성을 예측하는 강력한 힘을 가집니다. 연구에 따르면 변동성 곡률이 증가할 때 매수 신호를 생성하는 전략은 단순 보유 전략보다 높은 수익률을 기록했습니다. 또한, 시장이 비효율적인 가격 변동을 보일 때 다
음 시차에서 효율적인 부분으로 수렴하려는 경향은 개장 시간대의 거래량{{4}}과 밀접한 관련이 있습니다.수급 상관관계 및 미시구조 분석정보 기반 거래와 유동성 지표VPIN{{5}}(Volume-Synchronized Probability of Informed Trading) 지표는 정보에 정통한 투자자의 거래 비중을 측정하여 단기 변동성을 효과적으로 예측합니다. 고빈도 매매 환경에서 정보 유입 여부에 따라 바(bar)를 구성할 경우 통상적인 시간 기준 분석보다 예측력이 향상되는 것으로 나타났습니다. 스코어링 시스템은 이러한 미시구조{{6}} 데이터를 활용하여 수급의 질을 평가해야 합니다.해외 시장 전이 효과 및 역발상 전략미국 시장의 정보 전이 효과로 인해 코스피 200 지수는 장 초반 과잉 반응하는 경향이 있으며, 이는 장중 가격 반전으로 이어지기도 합니다. 이러한 오버슈팅{{7}} 현상을 활용한 데이트레이딩 전략은 유의미한 수익을 창출할 수 있는 근거가 됩니다. 또한 주식 가격은 시장 내 수요
와 공급의 법칙에 의해 결정되며, 특정 패턴을 통해 반복되는 경향을 보입니다.90일 시계열 패턴 및 알고리즘 설계패턴 기반 예측 및 머신러닝 모델과거 90일 이상의 시계열 데이터{{8}}를 활용하여 특정 가격 패턴과 거래량 변화를 분석함으로써 미래 지수 방향을 예측할 수 있습니다. CNN(합성곱 신경망) 모델을 이용한 캔들스틱 차트 이미지 분석은 갭 상승 및 하락을 약 55~58%의 정확도로 예측하며, 여기에 주요 투자자별 매매 동향을 추가하면 성능을 더욱 높일 수 있습니다. 서포트 벡터 머신{{9}}(SVM)과 유전 알고리즘을 결합한 시스템은 단순 지수 예측을 넘어 수익 극대화 신호를 생성하는 데 효과적입니다.투자자 행동 및 처분 효과 고려데이트레이더들은 손실 중인 종목을 보유하려는 처분 효과{{10}}를 보이며, 이는 폐장 직전 강제 손절매로 이어져 성과에 부정적인 영향을 미칩니다. 반면 성공적인 투자자들은 폐장 근처에서 이러한 강제 손실 실현을 최소화하는 특징을 보입니다. 따라서 알고리즘은 장 마감 시점의 수급 변화를 정밀하게 모니터링하여 양봉 마감 가능성을 점수화해야 합니다.알고리즘 매수 스코어링 시스템 제안알고리즘은 아래 4가지 핵심 요
소를 종합하여 0~100점 사이의 매수 점수를 산출합니다.
  <w:tblPr>
    <w:tblStyle w:val="a3"/>
    <w:tblW w:w="0" w:type="auto"/>
    <w:tblInd w:w="0" w:type="dxa"/>
    <w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>
    <w:tblBorders>
      <w:top w:val="single" w:sz="3" w:space="1" w:color="000000"/>
      <w:bottom w:val="single" w:sz="3" w:space="1" w:color="000000"/>
      <w:left w:val="single" w:sz="3" w:space="1" w:color="000000"/>
      <w:right w:val="single" w:sz="3" w:space="1" w:color="000000"/>
      <w:insideH w:val="single" w:sz="3" w:space="1" w:color="000000"/>
      <w:insideV w:val="single" w:sz="3" w:space="1" w:color="000000"/>
    </w:tblBorders>
  </w:tblPr>
  <w:tblLayout w:type="auto"/>
  <w:tblGrid>
    <w:gridCol w:w="2666"/>
    <w:gridCol w:w="2666"/>
    <w:gridCol w:w="2666"/>
  </w:tblGrid>
  <w:tr w:rsidR="00995B51" w:rsidTr="007F1D13">
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
        <w:shd w:val="clear" w:color="auto" w:fill="f5f5f5" w:themeFill="" w:themeFillTint=""/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>분석 항목
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
        <w:shd w:val="clear" w:color="auto" w:fill="f5f5f5" w:themeFill="" w:themeFillTint=""/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>가중치
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
        <w:shd w:val="clear" w:color="auto" w:fill="f5f5f5" w:themeFill="" w:themeFillTint=""/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>주요 평가 변수
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>가격 변동성
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>30%
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>VKOSPI 역상관관계, 옵션 변동성 곡률 변화, 일중
변동성 수렴도
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>수급 상관관계
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>30%
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>VPIN 기반 정보성 거래 비중, 거래량 가중
바(Bar) 패턴, 주체별 매매 동향
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>시계열 패턴
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>25%
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>90일 이동평균 및 캔들스틱 이미지 CNN 스코어,
미국 시장 전이 효과
    <w:tc>
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>미시 구조
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>15%
      <w:tcPr>
        <w:gridSpan w:val="1"/>
        <w:vAlign w:val="top"/>
        <w:tcW w:w="2666" w:type="dxa"/>
      </w:tcPr>
      <w:p w:rsidR="00995B51" w:rsidRPr="00722E63" w:rsidRDefault="00995B51">
        <w:pPr>
          <w:keepNext w:val="0"/>
          <w:keepLines w:val="0"/>
          <w:pageBreakBefore w:val="0"/>
          <w:widowControl/>
          <w:kinsoku/>
          <w:wordWrap/>
          <w:overflowPunct/>
          <w:topLinePunct w:val="0"/>
          <w:autoSpaceDE/>
          <w:autoSpaceDN/>
          <w:bidi w:val="0"/>
          <w:adjustRightInd/>
          <w:snapToGrid/>
          <w:spacing w:before="100" w:after="100" w:line="240" w:lineRule="atLeast"/>
          <w:jc w:val="left"/>
          <w:textAlignment w:val="auto"/>
        </w:pPr>
        <w:r w:rsidRPr="00722E63">
          <w:rPr>
            <w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>
            <w:color w:val="000000"/>
            <w:sz w:val="21"/>
            <w:szCs w:val="21"/>
          </w:rPr>
          <w:t>개장 초기 과잉 반응 해소 여부, 폐장 전 처분 효과에
따른 수급 변동면책 조항: 이 보고서는 일반적인 정보 제공을 목적으로 하며, 특정 종목에 대한 투자 권유나 금융 자문을 대신할 수 없습니다. 실제 투자 결정 전 반드시 전문가와 상의하시기 바랍니다.출처[1]  @article{???_2009, title={KOSPI 200 ??? ??? ??? ??? ??? ???}, url={https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001334976}, journal={The Royal Society of Chemistry’s Journals, Books and Databases (The Royal Society of Chemistry)}, author={???}, year={2009}, month=mar }[2]  @article{(4591705)(329325)(4591702)_(4591708)_2017a, title={Results of the KOSPI200 prediction based on [2] method.}, url={https://dx.plos.org/10.1371/journal.pone.0188107.t002}, journal={Figshare}, author={(4591705), Sujin Pyo and (329325), Jaewook Lee and (4591702), Mincheol Cha and (4591708), Huisu Jang}, year={2017}, month=nov }[3]  @article{(4591705)(329325)(4591702)_(4591708)_2017b, title={Results of the KOSPI200 prediction based on [2] method with 20-day and 30-day moving average.}, url={https://dx.plos.org/10.1371/journal.pone.0188107.t003}, journal={Figshare}, author={(4591705), Sujin Pyo and (329325), Jaewook Lee and (4591702), Mincheol Cha and (4591708), Huisu Jang}, year={2017}, month=nov }[4]  @article{Choi_2011, title={Do the Option Prices Forecast Spot Price? Evidence from the KOSPI 200 Index Option Market}, url={https://www.emerald.com/insight/content/doi/10.1108/JDQS-03-2011-B0002/full/html}, journal={Journal of Derivatives and Quantitative Studies 선물연구}, author={Choi, Byungwook}, year={2011}, month=aug }[5]  @article{Eom_2020, title={Intraday disposition effect of day traders and its relationship with investment performance: evidence from the KOSPI 200 futures market}, url={https://www.tandfonline.com/doi/full/10.1080/13504851.2019.1676374}, journal={Applied Economics Letters}, author={Eom, Yunsung}, year={2020}, month=aug }[6]  @article{Kang_Kwon_Kim_2020, title={Flow toxicity of high‐frequency trading and its impact on price volatility: Evidence from the KOSPI 200 futures market}, url={https://onlinelibrary.wiley.com/doi/10.1002/fut.22062}, journal={Journal of Futures Markets}, author={Kang, Jangkoo and Kwon, Kyung Yoon and Kim, Wooyeon}, year={2020}, month=feb }[7]  @article{Kim_Heung-Sik_Kim_2023, title={Price gap prediction using candlestick chart and convolutional neural network}, url={http://www.dbpia.co.kr/Journal/ArticleDetail/NODE11202361}, journal={Journal of the Korea Academia-Industrial cooperation Society}, author={Kim, Chansu and Heung-Sik, Choi and Kim, Sun-Woong}, year={2023}, month=jan }[8]  @article{Kim_Lee_2014, title={On the Importance of the Traders’ Rules for Pricing Options: Evidence From Intraday Data}, url={https://onlinelibrary.wiley.com/doi/10.1111/ajfs.12075}, journal={Asia-Pacific Journal of Financial Studies}, author={Kim, Sol and Lee, Changjun}, year={2014}, month=jan }[9]  @article{Kim_Ahn_2010, title={Development of an Intelligent Trading System Using Support Vector Machines and Genetic Algorithms}, url={https://www.koreascience.or.kr:443/article/JAKO201033538927039.pdf}, journal={Journal of Intelligence and Information Systems}, author={Kim, Sun Woong and Ahn, Hyunchul}, year={2010}, month=jan }[10]  @article{Kim_Choi_Lee_2010, title={A Study on Developing a Profitable Intra-day Trading System for KOSPI 200 Index Futures Using the US Stock Market Information Spillover Effect}, url={http://www.dbpia.co.kr/Journal/ArticleDetail/NODE01543700}, journal={Journal of Information Technology Applications and Management}, author={Kim, Sun Woong and Choi, Heung Sik and Lee, Byoung Hwa}, year={2010}, month=sept }[11]  @article{Ko_Lee_Chung_1995, title={Volatility, Efficiency, and Trading: Further Evidence}, url={https://onlinelibrary.wiley.com/doi/10.1111/j.1467-646X.1995.tb00048.x}, journal={Journal of International Financial Management and Accounting}, author={Ko, Kwangsoo and Lee, Sang Bin and Chung, Jee-Seok}, year={1995}, month=mar }[12]  @article{Lee_한치근_2003, title={패턴을 이용한 KOSPI200 예측 시스템}, url={http://www.dbpia.co.kr/Journal/ArticleDetail/NODE00616971?q=([주가 거래량§coldb§2§51§3])&fContentsType=14^_067001^_전자저널 논문&Multimedia=0&SearchAll=주가 거래량&isFullText=0&specificParam=0&SearchMethod=0&Sort=1&SortType=desc}, journal={한국정보과학회 학술발표논문집}, author={Lee, Jae-Young and 한치근}, year={2003}, month=oct }[13]  @article{Lee_Cho_Baek_2003, title={Trend detection using auto-associative neural networks: Intraday KOSPI 200 futures}, url={http://ieeexplore.ieee.org/document/1196290/}, author={Lee, Junmyung and Cho, Sungzoon and Baek, Jinwoo}, year={2003}, month=mar }[14]  @article{More_Bavdhane_Bartakke_Bari_Bargir, title={Pattern‑Based Analysis of Stock Movements Using Candlestick Charting Techniques}, url={https://www.scitepress.org/Papers/2025/141807/141807.pdf}, author={More, M and Bavdhane, K and Bartakke, V and Bari, S and Bargir, T} }[15]  @article{Mutinda_Yong_2026, title={Hybrid Prediction Framework Using Novel Stability-enhanced Dynamic Thresholding Feature Selection and Artificial Intelligence Methods for Financial Market Trend Prediction}, url={https://link.springer.com/article/10.1007/s10614-026-11346-3}, journal={Computational Economics}, author={Mutinda, JK and Yong, L}, year={2026}, month=jan }[16]  @article{Park_2007, title={The Profitability of Technical Trading Rules in the KOSPI200 Futures Market}, url={https://www.emerald.com/insight/content/doi/10.1108/JDQS-02-2007-B0004/full/html}, journal={Journal of Derivatives and Quantitative Studies 선물연구}, author={Park, Cheol Ho}, year={2007}, month=nov }[17]  @article{Sim_6315, title={Predicting Stock Market Crashes through Structural Properties of News: An Unsupervised Approach Beyond Sentiment Analysis}, url={https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6315438}, journal={Available at SSRN 6315438}, author={Sim, T}, year={6315}, month=jan }[18]  @article{박석진_정재식_2019, title={고빈도 자료를 이용한 머신러닝 모형의 예측력 비교 · 분석: KOSPI200 선물시장을 중심으로}, url={http://devkiss.kstudy.com/thesis/thesis-view.asp?key=3746588}, journal={금융연구}, author={박석진 and 정재식}, year={2019}, month=jan }[19]  @article{박종해_김태혁_변영태_서상구_2010, title={일중변동성 패턴에 따른 고빈도 분산비의 시계열 상관관계에 관한 연구}, url={http://dspace.kci.go.kr/handle/kci/770984}, journal={산업경제연구}, author={박종해 and 김태혁 and 변영태 and 서상구}, year={2010}, month=feb }[20]  @article{유재필_Joon_2014, title={시계열의 역상관관계를 이용한 KOSPI200 지수선물 매매 전략}, url={http://dspace.kci.go.kr/handle/kci/1440269?show=full}, journal={선물연구}, author={유재필 and Joon, Shin Hyun}, year={2014}, month=nov }[21]  @article{이정훈_2012, title={Analysis on Intraday Volatility from an Econophysics Perspective: Characteristics and Determinants}, url={http://hdl.handle.net/10371/156731}, journal={Seoul National University Open Repository (Seoul National University)}, author={이정훈}, year={2012}, month=jan }[22]  @misc{[Quiddity Index] KOSPI 200 Leaderboard for Jun26: Final Predictions_2026, url={https://www.smartkarma.com/insights/quiddity-index-kospi-200-leaderboard-for-jun26-final-predictions-4-adds-4-dels}, year={2026}, month=apr }[23]  @misc{7000 향해 질주하는 코스피…“5월에 팔고 떠나라” 통할까 - 네이트 뉴스_2026, url={https://news.nate.com/view/20260502n05627}, year={2026}, month=may }[24]  @misc{패턴을 이용한 KOSPI200 예측 시스템 - 한국정보과학회 학술발표논문집, url={https://www.dbpia.co.kr/journal/articleDetail?nodeId=NODE00616971} }[25]  @misc{Korean Data & Information Science Society - kdiss, url={https://www.kdiss.org/journal/list.html?pn=mostread} }[26]  @misc{Korean KOSPI 200 Trading Strategy – Backtest, Futures Example …, url={https://www.quantifiedstrategies.com/korean-kospi-200-trading-strategy/} }[27]  @misc{개요 - 한국증권학회, url={https://iksa.or.kr/homepage/custom/announce1} }
