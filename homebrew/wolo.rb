# Wolo Homebrew Formula
#
# Installation:
#   brew tap mbos-agent/wolo
#   brew install wolo
#
# Or directly from URL:
#   brew install --formula https://raw.githubusercontent.com/mbos-agent/wolo/main/homebrew/wolo.rb
#
class Wolo < Formula
  include Language::Python::Virtualenv

  desc "Minimal Python AI Agent CLI with MCP support"
  homepage "https://github.com/mbos-agent/wolo"
  url "https://files.pythonhosted.org/packages/source/m/mbos-wolo/mbos_wolo-0.1.0.tar.gz"
  sha256 ""  # Update this for each release
  license "Apache-2.0"
  head "https://github.com/mbos-agent/wolo.git", branch: "main"

  depends_on "python@3.12"

  def install
    # Create virtualenv and install wolo with all dependencies
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install_and_link(buildpath)
  end

  test do
    # Test that wolo can show help
    output = shell_output("#{bin}/wolo --help")
    assert_match "Wolo - AI Agent CLI", output
  end
end
