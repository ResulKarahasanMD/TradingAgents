import Foundation

enum WorkspaceLocator {
    static func defaultWorkspaceURL(filePath: String = #filePath) -> URL {
        if let override = ProcessInfo.processInfo.environment["TRADINGAGENTS_WORKSPACE"], !override.isEmpty {
            let url = URL(fileURLWithPath: override)
            if isWorkspaceRoot(url) {
                return url
            }
        }

        let bundleCandidate = Bundle.main.bundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        if isWorkspaceRoot(bundleCandidate) {
            return bundleCandidate
        }

        var candidate = URL(fileURLWithPath: filePath).deletingLastPathComponent()
        while candidate.path != "/" {
            if isWorkspaceRoot(candidate) {
                return candidate
            }
            candidate.deleteLastPathComponent()
        }

        let currentDirectory = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        return currentDirectory
    }

    static func isWorkspaceRoot(_ url: URL) -> Bool {
        let fileManager = FileManager.default
        let pyproject = url.appending(path: "pyproject.toml")
        let cliDirectory = url.appending(path: "cli", directoryHint: .isDirectory)
        let packageDirectory = url.appending(path: "tradingagents", directoryHint: .isDirectory)
        return fileManager.fileExists(atPath: pyproject.path)
            && fileManager.fileExists(atPath: cliDirectory.path)
            && fileManager.fileExists(atPath: packageDirectory.path)
    }
}
