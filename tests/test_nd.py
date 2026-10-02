"""North Dakota's exact original PDF cells and summary-table provenance."""
import io
from functools import lru_cache

import pytest
from pypdf import PdfReader, PdfWriter

from sdo_mcp import server,store
from sdo_mcp.ingest import nd


@lru_cache
def _body():
    return (nd.RAW_DIR/nd.FILE).read_bytes()


@lru_cache
def _reader():
    return PdfReader(io.BytesIO(_body()))


def _tokens():
    return [nd._text_tokens(_reader().pages[i]) for i in nd.SUMMARY_PAGES]


def test_state_selected_table_grid_and_discrepancy():
    result=server.get_forecast("ND","state","North Dakota","population")
    assert result["status"]=="ok"
    assert result["series"]==[dict(year=y,value=v,datatype="estimate" if y==2020 else "projection")
                              for y,v in zip(nd.YEARS,nd.STATE_VALUES,strict=True)]
    source=result["source"]
    assert source["vintage"]=="February 6, 2024" and source["base_year"]==2020
    assert source["horizon_year"]==2050 and source["retrieved_at"]=="2026-10-02"
    assert source["url"]==nd.URL
    assert "957,124" in source["method_notes"] and "957,194" in source["method_notes"]
    assert "printed pp10-11" in source["citation"]


@pytest.mark.parametrize("name,gid,year,value",[
    ("Cass","38017",2020,184525),("Cass","38017",2025,194767),("Cass","38017",2050,272878),
    ("Slope","38087",2020,706),("Slope","38087",2025,713),("Slope","38087",2050,799),
    ("Golden Valley","38033",2050,1720),("Williams","38105",2050,56047),
])
def test_county_name_id_and_rendered_anchors(name,gid,year,value):
    result=server.get_forecast("ND","county",name,"population",year,year)
    assert result==server.get_forecast("ND","county",gid,"population",year,year)
    assert result["series"]==[dict(year=year,value=value,datatype="estimate" if year==2020 else "projection")]


def test_all_county_points_rounding_and_deferred_products():
    conn=store.connect()
    try:
        nd.verify(conn)
        assert conn.execute("SELECT COUNT(DISTINCT geo_id) FROM observations WHERE state='ND' AND geo_level='county'").fetchone()[0]==53
    finally:
        conn.close()
    assert server.get_forecast("ND","economic_region","Fargo","population")["status"]=="not_loaded"
    assert server.get_forecast("ND","place","Fargo","population")["status"]=="coverage_unknown"
    assert server.get_components("ND","ND")["status"]=="pdf_only"
    assert server.get_components("ND","Cass")["status"]=="coverage_unknown"
    for variable in ("households","employment"):
        assert server.get_forecast("ND","county","Cass",variable)["status"]=="coverage_unknown"
    assert server.describe_source("ND")["review"]["status"]=="never_reviewed"


@pytest.mark.parametrize("start,end",[(2021,2024),(2026,2029),(2051,2060)])
def test_gaps_do_not_interpolate(start,end):
    result=server.get_forecast("ND","state","ND","population",start,end)
    assert result["status"]=="empty_range"
    assert result["available_start_year"]==2020 and result["available_end_year"]==2050


def test_invalid_scenario_and_unknown_geography():
    assert server.get_forecast("ND","state","ND","population",scenario="High")["status"]=="error"
    result=server.get_forecast("ND","county","No such county","population")
    assert result["status"]=="error" and result["candidates"] is None
    ambiguous=server.get_forecast("ND","county","Mc","population")
    assert ambiguous["status"]=="error" and len(ambiguous["candidates"])==4


def test_kerning_operations_preserve_exact_original_numeric_cells():
    # Ordinary text extraction inserts spaces within numeric cells, e.g.
    # Adams'2025 2,120. Original text-show operands preserve its digit glyphs.
    assert "2 ,12 0" in _reader().pages[9].extract_text()
    assert _tokens()[0][_tokens()[0].index("Adams County")+2]=="2,120"
    assert len(nd._parse_summary(_tokens()))==378
    assert nd._check_state_table(nd._text_tokens(_reader().pages[13]))==nd.STATE_VALUES


@pytest.mark.parametrize("old,new,error",[
    ("Adams County","Unknown County","unknown geography"),
    ("Barnes County","Adams County","duplicate"),
    ("2,200","NA","integer"),("2,200","-1","integer"),
    ("2,200","2.200","integer"),("2,200","2,20","integer"),
    ("2,200","2,201","rounding difference"),
    ("957,194","957,124","state totals"),
])
def test_corrupted_original_cells_rejected(old,new,error):
    pages=_tokens()
    changed=False
    for tokens in pages:
        if old in tokens:
            tokens[tokens.index(old)]=new
            changed=True
            break
    assert changed
    with pytest.raises(ValueError,match=error):nd._parse_summary(pages)


def test_missing_county_year_header_and_wrapped_label_rejected():
    pages=_tokens();del pages[0][1:9]
    with pytest.raises(ValueError,match="incomplete"):nd._parse_summary(pages)
    pages=_tokens();pages[1][-1]="2051"
    with pytest.raises(ValueError,match="year grid"):nd._parse_summary(pages)
    pages=_tokens();pages[0][pages[0].index("Golden Valley")+1]="Parish"
    with pytest.raises(ValueError,match="Golden Valley"):nd._parse_summary(pages)
    with pytest.raises(ValueError,match="incomplete"):nd._parse_summary(_tokens()[:1])


def test_repeated_independent_state_total_disagreement_rejected():
    tokens=nd._text_tokens(_reader().pages[13]);tokens[tokens.index("Total")+7]="957,124"
    with pytest.raises(ValueError,match="Total disagrees"):nd._check_state_table(tokens)


@pytest.mark.parametrize("page,old,new",[(0,"February 6, 2024","February 6, 2025"),(4,"Census 2020","Census 2010")])
def test_changed_edition_and_census_base_rejected(page,old,new):
    texts={i:_reader().pages[i].extract_text() for i in (0,4)}
    assert old in texts[page];texts[page]=texts[page].replace(old,new)
    with pytest.raises(ValueError,match="edition or Census base"):nd._validate_edition(texts[0],texts[4])


@pytest.mark.parametrize("body",[b"<html>temporary error</html>",b"[]",b"%PDF broken"])
def test_soft_200_rejected(body):
    with pytest.raises(ValueError,match="readable population PDF"):nd.parse(body)


def test_wrong_readable_pdf_rejected():
    output=io.BytesIO();writer=PdfWriter();writer.add_blank_page(612,792);writer.write(output)
    with pytest.raises(ValueError,match="page count"):nd.parse(output.getvalue())


def test_snapshot_reuse_without_network_or_new_retrieval(monkeypatch):
    original=(nd.RAW_DIR/"manifest.json").read_bytes()
    monkeypatch.setattr(nd.fetch,"get_bytes",lambda *_:pytest.fail("unexpected network"))
    nd.acquire()
    assert (nd.RAW_DIR/"manifest.json").read_bytes()==original


@pytest.mark.parametrize("file",list(nd.FILES))
def test_invalid_acquisition_archives_nothing(file,tmp_path,monkeypatch):
    bodies={n:(nd.RAW_DIR/n).read_bytes() for n in nd.FILES};bodies[file]=b"<html>temporary error</html>"
    monkeypatch.setattr(nd,"RAW_DIR",tmp_path/"nd")
    monkeypatch.setattr(nd.fetch,"get_bytes",lambda url:bodies[next(n for n,v in nd.FILES.items() if v==url)])
    with pytest.raises(ValueError,match="catalog|readable population PDF"):nd.acquire()
    assert not nd.RAW_DIR.exists()


def test_missing_seeded_geography_prevents_load(tmp_path):
    conn=store.connect(tmp_path/"db.sqlite",create=True)
    try:
        store.init_db(conn)
        with pytest.raises(ValueError,match="seeded geographies"):nd.load(conn)
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]==0
    finally:conn.close()
