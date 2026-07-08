class AiDataPlatform < Formula
  include Language::Python::Virtualenv

  desc "AI Data Platform: synthetic data, catalog, semantic models, MCP server"
  homepage "https://github.com/Yogi776/data-generation-sdk"
  url "https://files.pythonhosted.org/packages/PLACEHOLDER/ai_data_platform-PLACEHOLDER.tar.gz"
  sha256 "PLACEHOLDER"
  license "Apache-2.0"

  depends_on "python@3.12"

{{poet_resources}}

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/adp version")
    shell_output("#{bin}/adp --help")
    shell_output("#{bin}/adp mcp-server --help")
    cd testpath do
      system bin/"adp", "init", "--name", "brew-smoke"
      assert_path_exists testpath/"adp.yaml"
    end
  end
end
