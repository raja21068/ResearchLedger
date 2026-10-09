from researchledger.workspace import Workspace, init_workspace


def test_workspace_properties_point_at_the_right_paths(tmp_path):
    ws = Workspace(tmp_path)
    assert ws.project_file == tmp_path / "project.md"
    assert ws.state_file == tmp_path / "research-state.md"
    assert ws.plans_dir == tmp_path / "plans"
    assert ws.papers_dir == tmp_path / "papers"


def test_is_workspace_true_after_init(tmp_path):
    ws = init_workspace(tmp_path)
    assert ws.is_workspace() is True


def test_is_workspace_false_for_an_untouched_directory(tmp_path):
    assert Workspace(tmp_path).is_workspace() is False
