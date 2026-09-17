import Foundation

struct BridgeError: LocalizedError {
    let message: String

    var errorDescription: String? { message }
}

final class RunningBridgeHandle {
    private let process: Process
    private let stdoutTask: Task<Void, Never>
    private let stderrTask: Task<Void, Never>
    private let cleanup: () -> Void

    init(process: Process, stdoutTask: Task<Void, Never>, stderrTask: Task<Void, Never>, cleanup: @escaping () -> Void) {
        self.process = process
        self.stdoutTask = stdoutTask
        self.stderrTask = stderrTask
        self.cleanup = cleanup
    }

    func terminate() {
        stdoutTask.cancel()
        stderrTask.cancel()
        if process.isRunning {
            process.terminate()
        }
        cleanup()
    }

    deinit {
        cleanup()
    }
}

@MainActor
final class TradingAgentsBridge {
    private let decoder = JSONDecoder()

    func loadCatalog(workspaceURL: URL) async throws -> BridgeCatalog {
        let process = makeBaseProcess(workspaceURL: workspaceURL, arguments: ["options"])
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        try process.run()
        let data = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()

        guard process.terminationStatus == 0 else {
            let details = String(decoding: stderrData, as: UTF8.self)
            throw BridgeError(message: details.isEmpty ? "Failed to load bridge catalog." : details)
        }

        return try decoder.decode(BridgeCatalog.self, from: data)
    }

    func startAnalysis(
        workspaceURL: URL,
        payload: [String: Any],
        onEvent: @escaping @MainActor (BridgeRunEvent) -> Void,
        onDiagnostic: @escaping @MainActor (String) -> Void,
        onTermination: @escaping @MainActor (Int32) -> Void
    ) throws -> RunningBridgeHandle {
        let requestFile = try writeRequestFile(payload: payload)
        let process = makeBaseProcess(
            workspaceURL: workspaceURL,
            arguments: ["run", "--request-file", requestFile.path]
        )

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        process.terminationHandler = { process in
            Task { @MainActor in
                onTermination(process.terminationStatus)
            }
        }

        try process.run()

        let decoder = JSONDecoder()

        let stdoutTask = Task {
            do {
                for try await line in stdoutPipe.fileHandleForReading.bytes.lines {
                    guard let data = line.data(using: .utf8) else { continue }
                    do {
                        let event = try decoder.decode(BridgeRunEvent.self, from: data)
                        onEvent(event)
                    } catch {
                        onDiagnostic("Bridge output could not be decoded: \(line)")
                    }
                }
            } catch {
                onDiagnostic("Stopped reading bridge output: \(error.localizedDescription)")
            }
        }

        let stderrTask = Task {
            do {
                for try await line in stderrPipe.fileHandleForReading.bytes.lines where !line.isEmpty {
                    onDiagnostic(line)
                }
            } catch {
                onDiagnostic("Stopped reading bridge diagnostics: \(error.localizedDescription)")
            }
        }

        let cleanup: () -> Void = {
            try? FileManager.default.removeItem(at: requestFile)
        }

        return RunningBridgeHandle(
            process: process,
            stdoutTask: stdoutTask,
            stderrTask: stderrTask,
            cleanup: cleanup
        )
    }

    private func makeBaseProcess(workspaceURL: URL, arguments: [String]) -> Process {
        let process = Process()
        process.currentDirectoryURL = workspaceURL
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["uv", "run", "python", "-m", "cli.macos_bridge"] + arguments

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment
        return process
    }

    private func writeRequestFile(payload: [String: Any]) throws -> URL {
        let data = try JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted])
        let fileURL = FileManager.default.temporaryDirectory
            .appending(path: "tradingagents-\(UUID().uuidString).json")
        try data.write(to: fileURL)
        return fileURL
    }
}
