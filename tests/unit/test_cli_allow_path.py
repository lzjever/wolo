from wolo.cli.parser import FlexibleArgumentParser


def test_parse_allow_path_long_and_short():
    parser = FlexibleArgumentParser()
    args = parser.parse(
        ["-P", "/workspace", "--allow-path", "/data", "task"],
        check_stdin=False,
    )
    assert args.execution_options.allow_paths == ["/workspace", "/data"]


def test_parse_allow_path_preserves_order_and_deduplicates():
    parser = FlexibleArgumentParser()
    args = parser.parse(
        [
            "--allow-path",
            "/workspace",
            "-P",
            "/data",
            "--allow-path",
            "/workspace",
            "task",
        ],
        check_stdin=False,
    )
    assert args.execution_options.allow_paths == ["/workspace", "/data"]


def test_allow_path_defaults_to_empty():
    parser = FlexibleArgumentParser()
    args = parser.parse(["task"], check_stdin=False)
    assert args.execution_options.allow_paths == []


def test_parse_wild_mode_flag():
    parser = FlexibleArgumentParser()
    args = parser.parse(["--wild", "task"], check_stdin=False)
    assert args.execution_options.wild_mode is True
    assert args.execution_options.wild_mode_explicit is True


def test_parse_wild_mode_short_flag():
    parser = FlexibleArgumentParser()
    args = parser.parse(["-W", "task"], check_stdin=False)
    assert args.execution_options.wild_mode is True
    assert args.execution_options.wild_mode_explicit is True


def test_parse_wild_mode_default_not_explicit():
    parser = FlexibleArgumentParser()
    args = parser.parse(["task"], check_stdin=False)
    assert args.execution_options.wild_mode is False
    assert args.execution_options.wild_mode_explicit is False
