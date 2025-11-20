import argparse

import jpype
import jpype.imports
from rag.cleaning import clean_common_noise, clean_rag_text


def hwpx_extract(file_path):
    try:
        ## jpype 시작
        jpype.startJVM(convertStrings=True)

        ## java package 가져오기
        from kr.dogfoot.hwpxlib.reader import HWPXReader
        from kr.dogfoot.hwpxlib.tool.textextractor import (
            TextExtractMethod,
            TextExtractor,
            TextMarks,
        )

        hwpx_file = HWPXReader.fromFilepath(file_path)
        text_extract_method = TextExtractMethod.InsertControlTextBetweenParagraphText
        text_marks = (
            TextMarks()
            .lineBreakAnd("\n")
            .paraSeparatorAnd("\n\n")
            .tableStartAnd("<table>\n")
            .tableEndAnd("\n</table>")
            .tabAnd("\t")
            .containerStartAnd("\n\n")
            .containerEndAnd("\n\n")
            .fieldStartAnd("")
            .fieldEndAnd("")
        )

        # 한글 추출
        hwpxtext = TextExtractor.extract(
            hwpx_file, text_extract_method, True, text_marks
        )
        hwpxtext = clean_rag_text(hwpxtext)
        hwpxtext = clean_common_noise(hwpxtext)

    except Exception as e:
        hwpxtext = "Error Occurred: " + str(e)
    finally:
        jpype.shutdownJVM()
    return hwpxtext


if __name__ == "__main__":
    # 파라미터 파싱
    parser = argparse.ArgumentParser(description="Hwpx extractor")
    parser.add_argument(
        "--file_path",
        type=str,
        default="/app/test/testfiles/2023년 디지털정부 발전유공 포상 추진계획.hwpx",
        help="hwpx 파일 경로",
    )
    args = parser.parse_args()

    hwp_text = hwpx_extract(args.file_path)

    # print로 표준출력
    print(hwp_text)