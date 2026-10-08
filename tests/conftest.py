"""Fake icon packages built in memory from hand-written SVGs: tests never touch the network."""

import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest
import yaml

from archdiagram import icons
from archdiagram.spec import parse

FIX = Path(__file__).parent / "fixtures"


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def make_tgz(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def spec_from(text: str):
    return parse(yaml.safe_load(text))


@pytest.fixture
def empty_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHDIAGRAM_CACHE", str(tmp_path))
    return tmp_path


@pytest.fixture
def cache(empty_cache):
    """aws + generic from one fake AWS-style zip, brand from a fake npm tarball."""
    service, glyph, styled = ((FIX / n).read_bytes() for n in ("service.svg", "glyph.svg", "styled.svg"))
    aws, generic, brand = icons.get_pack("aws"), icons.get_pack("generic"), icons.get_pack("brand")
    aws_zip = make_zip({
        aws.aliases["lambda"]: service,
        aws.aliases["ddb"]: service,
        aws.aliases["apigw"]: styled,
        generic.aliases["users"]: glyph,
        "__MACOSX/" + aws.aliases["s3"]: service,
        "../escape.svg": service,
    })
    icons.fetch(aws, download=lambda url: aws_zip)
    icons.fetch(generic, download=lambda url: aws_zip)
    colors = [{"slug": "jira", "hex": "0052CC"}, {"slug": "lambda", "hex": "FF9900"}, {"slug": "notion", "hex": "000000"}]
    brand_tgz = make_tgz({
        "package/icons/jira.svg": (FIX / "brand.svg").read_bytes(),
        "package/icons/lambda.svg": (FIX / "brand.svg").read_bytes(),
        "package/icons/notion.svg": (FIX / "brand.svg").read_bytes(),
        "package/data/simple-icons.json": json.dumps(colors).encode(),
    })
    icons.fetch(brand, download=lambda url: brand_tgz)
    return empty_cache
