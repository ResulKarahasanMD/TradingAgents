import AppKit
import Foundation
import Observation

@MainActor
@Observable
final class AppModel {
    let agentTeams: [(name: String, agents: [String])] = [
        ("Analyst Team", ["Market Analyst", "Social Analyst", "News Analyst", "Fundamentals Analyst"]),
        ("Research Team", ["Bull Researcher", "Bear Researcher", "Research Manager"]),
        ("Trading Team", ["Trader"]),
        ("Risk Management", ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"]),
        ("Portfolio Management", ["Portfolio Manager"]),
    ]

    var workspacePath: String
    var resultsRootPath: String

    var ticker = "SPY"
    var analysisDate = Date()
    var selectedAnalysts: Set<String> = ["market", "social", "news", "fundamentals"]
    var researchDepth = 1
    var provider = "openai"
    var backendURL = "https://api.openai.com/v1"
    var quickModel = "gpt-5.4-mini"
    var deepModel = "gpt-5.4"
    var customQuickModel = ""
    var customDeepModel = ""
    var outputLanguage = "English"
    var customOutputLanguage = ""
    var openAIReasoningEffort = "medium"
    var anthropicEffort = "high"
    var googleThinkingLevel = "high"

    var catalog: BridgeCatalog?
    var snapshot: BridgeSnapshot?
    var decision: String?
    var reportFilePath: String?
    var resultsDirectoryPath: String?
    var runError: String?
    var diagnostics: [String] = []
    var isLoadingCatalog = false
    var isRunning = false
    var statusLine = "Loading TradingAgents bridge…"

    private let bridge = TradingAgentsBridge()
    private var runningHandle: RunningBridgeHandle?

    init() {
        let workspaceURL = WorkspaceLocator.defaultWorkspaceURL()
        workspacePath = workspaceURL.path
        resultsRootPath = workspaceURL.appending(path: "results", directoryHint: .isDirectory).path
    }

    var workspaceURL: URL {
        URL(fileURLWithPath: workspacePath.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    var currentProvider: ProviderCatalog? {
        catalog?.providers.first(where: { $0.value == provider })
    }

    var availableQuickModels: [OptionChoice] {
        currentProvider?.quickModels ?? []
    }

    var availableDeepModels: [OptionChoice] {
        currentProvider?.deepModels ?? []
    }

    var supportsCustomModels: Bool {
        currentProvider?.supportsCustomModels ?? false
    }

    var resolvedQuickModel: String {
        supportsCustomModels ? customQuickModel.trimmingCharacters(in: .whitespacesAndNewlines) : quickModel
    }

    var resolvedDeepModel: String {
        supportsCustomModels ? customDeepModel.trimmingCharacters(in: .whitespacesAndNewlines) : deepModel
    }

    var resolvedOutputLanguage: String {
        outputLanguage == "custom"
            ? customOutputLanguage.trimmingCharacters(in: .whitespacesAndNewlines)
            : outputLanguage
    }

    var validationMessage: String? {
        let fileManager = FileManager.default
        if ticker.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "Ticker is required."
        }
        if selectedAnalysts.isEmpty {
            return "Select at least one analyst."
        }
        if !fileManager.fileExists(atPath: workspaceURL.path) {
            return "Workspace path does not exist."
        }
        if resolvedQuickModel.isEmpty || resolvedDeepModel.isEmpty {
            return "Choose both quick and deep thinking models."
        }
        if resolvedOutputLanguage.isEmpty {
            return "Choose an output language."
        }
        return nil
    }

    var canStart: Bool {
        !isRunning && validationMessage == nil
    }

    func loadCatalogIfNeeded() {
        guard catalog == nil && !isLoadingCatalog else { return }
        loadCatalog()
    }

    func loadCatalog() {
        isLoadingCatalog = true
        runError = nil
        diagnostics.removeAll()
        statusLine = "Loading bridge options…"

        Task {
            do {
                let catalog = try await bridge.loadCatalog(workspaceURL: workspaceURL)
                applyCatalog(catalog)
                statusLine = "Bridge ready."
            } catch {
                runError = error.localizedDescription
                statusLine = "Bridge failed to load."
            }
            isLoadingCatalog = false
        }
    }

    func providerDidChange() {
        syncProviderSelection(forceReset: true)
    }

    func setAnalyst(_ analyst: String, enabled: Bool) {
        if enabled {
            selectedAnalysts.insert(analyst)
        } else {
            selectedAnalysts.remove(analyst)
        }
    }

    func startAnalysis() {
        guard let validationMessage else {
            runError = nil
            decision = nil
            reportFilePath = nil
            resultsDirectoryPath = nil
            diagnostics.removeAll()
            snapshot = nil
            statusLine = "Starting analysis…"

            let payload = buildRequestPayload()
            do {
                runningHandle = try bridge.startAnalysis(
                    workspaceURL: workspaceURL,
                    payload: payload,
                    onEvent: { [weak self] event in
                        self?.consume(event)
                    },
                    onDiagnostic: { [weak self] diagnostic in
                        self?.diagnostics.append(diagnostic)
                    },
                    onTermination: { [weak self] status in
                        guard let self else { return }
                        self.isRunning = false
                        if status != 0 && self.runError == nil {
                            self.statusLine = "Bridge exited with status \(status)."
                        }
                    }
                )
                isRunning = true
            } catch {
                runError = error.localizedDescription
                statusLine = "Failed to start analysis."
            }
            return
        }

        runError = validationMessage
    }

    func cancelAnalysis() {
        runningHandle?.terminate()
        runningHandle = nil
        isRunning = false
        statusLine = "Analysis cancelled."
    }

    func openResultsDirectory() {
        guard let path = resultsDirectoryPath else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }

    func openReportFile() {
        guard let path = reportFilePath else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }

    private func applyCatalog(_ catalog: BridgeCatalog) {
        self.catalog = catalog
        provider = catalog.defaultProvider
        quickModel = catalog.defaultQuickModel
        deepModel = catalog.defaultDeepModel
        outputLanguage = catalog.defaultOutputLanguage
        if let date = Self.parseDate(catalog.defaultDate) {
            analysisDate = date
        }
        syncProviderSelection(forceReset: false)
    }

    private func syncProviderSelection(forceReset: Bool) {
        guard let currentProvider else { return }

        if forceReset || backendURL.isEmpty {
            backendURL = currentProvider.baseURL ?? ""
        }

        if currentProvider.supportsCustomModels {
            if forceReset || customQuickModel.isEmpty {
                customQuickModel = quickModel
            }
            if forceReset || customDeepModel.isEmpty {
                customDeepModel = deepModel
            }
            return
        }

        if forceReset || !currentProvider.quickModels.contains(where: { $0.value == quickModel }) {
            quickModel = currentProvider.quickModels.first?.value ?? ""
        }
        if forceReset || !currentProvider.deepModels.contains(where: { $0.value == deepModel }) {
            deepModel = currentProvider.deepModels.first?.value ?? ""
        }
    }

    private func buildRequestPayload() -> [String: Any] {
        [
            "ticker": ticker.trimmingCharacters(in: .whitespacesAndNewlines),
            "analysis_date": Self.formatDate(analysisDate),
            "analysts": agentTeams
                .flatMap(\.agents)
                .compactMap { displayName in
                    switch displayName {
                    case "Market Analyst": return "market"
                    case "Social Analyst": return "social"
                    case "News Analyst": return "news"
                    case "Fundamentals Analyst": return "fundamentals"
                    default: return nil
                    }
                }
                .filter { selectedAnalysts.contains($0) },
            "research_depth": researchDepth,
            "llm_provider": provider,
            "backend_url": backendURL.isEmpty ? NSNull() : backendURL,
            "shallow_thinker": resolvedQuickModel,
            "deep_thinker": resolvedDeepModel,
            "google_thinking_level": googleThinkingLevel,
            "openai_reasoning_effort": openAIReasoningEffort,
            "anthropic_effort": anthropicEffort,
            "output_language": resolvedOutputLanguage,
            "results_root": resultsRootPath,
        ]
    }

    private func consume(_ event: BridgeRunEvent) {
        switch event.event {
        case "snapshot":
            snapshot = event.snapshot
            if let snapshot {
                statusLine = "Running \(snapshot.ticker) for \(snapshot.analysisDate)…"
            }
        case "completed":
            snapshot = event.snapshot
            decision = event.decision
            reportFilePath = event.reportFile
            resultsDirectoryPath = event.resultsDirectory
            isRunning = false
            runningHandle = nil
            statusLine = "Analysis complete."
        case "error":
            runError = event.message ?? "Unknown bridge error."
            if let details = event.details, !details.isEmpty {
                diagnostics.append(details)
            }
            isRunning = false
            runningHandle = nil
            statusLine = "Analysis failed."
        default:
            break
        }
    }

    private static func parseDate(_ string: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate]
        return formatter.date(from: string)
    }

    private static func formatDate(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate]
        return formatter.string(from: date)
    }
}
