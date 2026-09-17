import Foundation

struct OptionChoice: Codable, Hashable, Identifiable {
    let label: String
    let value: String

    var id: String { value }
}

struct AnalystOption: Codable, Hashable, Identifiable {
    let value: String
    let title: String
    let summary: String

    var id: String { value }
}

struct ResearchDepthOption: Codable, Hashable, Identifiable {
    let label: String
    let value: Int
    let summary: String

    var id: Int { value }
}

struct ProviderCatalog: Codable, Hashable, Identifiable {
    let name: String
    let value: String
    let baseURL: String?
    let supportsCustomModels: Bool
    let quickModels: [OptionChoice]
    let deepModels: [OptionChoice]

    enum CodingKeys: String, CodingKey {
        case name
        case value
        case baseURL = "base_url"
        case supportsCustomModels = "supports_custom_models"
        case quickModels = "quick_models"
        case deepModels = "deep_models"
    }

    var id: String { value }
}

struct BridgeCatalog: Codable {
    let defaultDate: String
    let defaultProvider: String
    let defaultQuickModel: String
    let defaultDeepModel: String
    let defaultOutputLanguage: String
    let analysts: [AnalystOption]
    let providers: [ProviderCatalog]
    let researchDepths: [ResearchDepthOption]
    let outputLanguages: [OptionChoice]
    let openAIReasoningEfforts: [OptionChoice]
    let anthropicEfforts: [OptionChoice]
    let googleThinkingLevels: [OptionChoice]

    enum CodingKeys: String, CodingKey {
        case defaultDate = "default_date"
        case defaultProvider = "default_provider"
        case defaultQuickModel = "default_quick_model"
        case defaultDeepModel = "default_deep_model"
        case defaultOutputLanguage = "default_output_language"
        case analysts
        case providers
        case researchDepths = "research_depths"
        case outputLanguages = "output_languages"
        case openAIReasoningEfforts = "openai_reasoning_efforts"
        case anthropicEfforts = "anthropic_efforts"
        case googleThinkingLevels = "google_thinking_levels"
    }
}

enum JSONValue: Codable, Hashable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON payload.")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .number(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        case .object(let value):
            try container.encode(value)
        case .array(let value):
            try container.encode(value)
        case .null:
            try container.encodeNil()
        }
    }

    var rendered: String {
        switch self {
        case .string(let value):
            return value
        case .number(let value):
            return String(value)
        case .bool(let value):
            return value ? "true" : "false"
        case .object(let value):
            let pairs = value.keys.sorted().map { key in
                "\(key): \(value[key]?.rendered ?? "")"
            }
            return "{ " + pairs.joined(separator: ", ") + " }"
        case .array(let value):
            return "[" + value.map(\.rendered).joined(separator: ", ") + "]"
        case .null:
            return "null"
        }
    }
}

struct BridgeLogEntry: Codable, Hashable, Identifiable {
    let id: String
    let timestamp: String
    let kind: String
    let content: String
}

struct BridgeToolCall: Codable, Hashable, Identifiable {
    let id: String
    let timestamp: String
    let name: String
    let args: JSONValue?

    var formattedArgs: String {
        args?.rendered ?? "{}"
    }
}

struct BridgeStats: Codable, Hashable {
    let llmCalls: Int
    let toolCalls: Int
    let tokensIn: Int
    let tokensOut: Int

    enum CodingKeys: String, CodingKey {
        case llmCalls = "llm_calls"
        case toolCalls = "tool_calls"
        case tokensIn = "tokens_in"
        case tokensOut = "tokens_out"
    }
}

struct BridgeSnapshot: Codable, Hashable {
    let ticker: String
    let analysisDate: String
    let agentStatuses: [String: String]
    let messages: [BridgeLogEntry]
    let toolCalls: [BridgeToolCall]
    let currentReportTitle: String?
    let currentReportMarkdown: String?
    let finalReportMarkdown: String?
    let reportsCompleted: Int
    let reportsTotal: Int
    let elapsedSeconds: Double
    let stats: BridgeStats

    enum CodingKeys: String, CodingKey {
        case ticker
        case analysisDate = "analysis_date"
        case agentStatuses = "agent_statuses"
        case messages
        case toolCalls = "tool_calls"
        case currentReportTitle = "current_report_title"
        case currentReportMarkdown = "current_report_markdown"
        case finalReportMarkdown = "final_report_markdown"
        case reportsCompleted = "reports_completed"
        case reportsTotal = "reports_total"
        case elapsedSeconds = "elapsed_seconds"
        case stats
    }
}

struct BridgeRunEvent: Codable {
    let event: String
    let snapshot: BridgeSnapshot?
    let resultsDirectory: String?
    let reportFile: String?
    let decision: String?
    let message: String?
    let details: String?

    enum CodingKeys: String, CodingKey {
        case event
        case snapshot
        case resultsDirectory = "results_directory"
        case reportFile = "report_file"
        case decision
        case message
        case details
    }
}
