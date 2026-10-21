import SwiftUI
public import Combine

// MARK: - Cross-Platform Color Helpers

extension Color {
    #if os(macOS)
    static let chatBackground = Color(nsColor: .windowBackgroundColor)
    static let cardBackground = Color(nsColor: .controlBackgroundColor)
    #else
    static let chatBackground = Color(uiColor: .systemGroupedBackground)
    static let cardBackground = Color(uiColor: .secondarySystemGroupedBackground)
    #endif
}

// MARK: - Models

struct CropCardModel: Identifiable, Equatable {
    let id = UUID()
    let crop: String
    let profit: Double
    let fit: Double
    let yield: Double
    let waterGap: Double
    let why: [String]
    let cautions: [String]
}

struct PlanStepModel: Identifiable, Equatable {
    let id = UUID()
    let season: String
    let crop: String
    let soilHealth: Int
}

struct TaskItemModel: Identifiable, Equatable {
    let id = UUID()
    let date: String
    let task: String
}

struct PlanSummaryModel: Equatable {
    let rotation: [PlanStepModel]
    let tasks: [TaskItemModel]
    let totalProfit: Double
}

struct Message: Identifiable, Equatable {
    let id = UUID()
    let text: String
    let isUser: Bool
    let timestamp: Date = Date()
    var quickReplies: [String] = []
    var crops: [CropCardModel]? = nil
    var plan: PlanSummaryModel? = nil
    var stateDefaultsNote: String? = nil
}

struct FarmProfile: Equatable {
    var state: String? = nil
    var soilType: String? = nil
    var soilSource: String? = nil
    var irrigated: Bool? = nil
    var irrigatedSource: String? = nil
    var acres: Double? = nil
    var capitalPerAcre: Double? = nil
    var riskTolerance: String? = nil
    var sowingDate: String? = nil

    var isConfigured: Bool {
        state != nil
    }
}

// MARK: - View Model

@MainActor
class ChatViewModel: ObservableObject {
    @Published var messages: [Message] = []
    @Published var inputText: String = ""
    @Published var isLoading: Bool = false
    @Published var profile: FarmProfile = FarmProfile()
    @Published var isServerOnline: Bool = false
    @Published var serverURL: String = "https://crop.mehul.sbs"

    private var profileDict: [String: Any] = [:]
    private var apiKey: String {
        UserDefaults.standard.string(forKey: "CropAdvisorAPIKey") ?? ""
    }

    init() {
        // Welcome message
        let welcome = Message(
            text: "Namaste! Welcome to Crop Advisor. Tell me about your farm (e.g., 'I have land in Goa' or '5 acres in Punjab, loam soil, irrigated') and I will calculate the best crop recommendations for you.",
            isUser: false,
            quickReplies: [
                "🌴 I have land in Goa",
                "🌾 5 acres in Punjab, irrigated",
                "🌱 Karnataka, 4 acres red soil, borewell",
                "🌧️ Maharashtra, black soil, rainfed",
                "📋 Show full 6-season plan"
            ]
        )
        messages.append(welcome)
        Task {
            await checkHealth()
        }
    }

    func checkHealth() async {
        guard let url = URL(string: "\(serverURL)/health") else { return }
        var request = URLRequest(url: url)
        request.timeoutInterval = 2.0
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let httpRes = response as? HTTPURLResponse, httpRes.statusCode == 200 {
                isServerOnline = true
            } else {
                isServerOnline = false
            }
        } catch {
            isServerOnline = false
        }
    }

    func sendCurrentInput() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""
        sendMessage(text)
    }

    func sendQuickReply(_ text: String) {
        sendMessage(text)
    }

    func sendMessage(_ text: String) {
        let userMsg = Message(text: text, isUser: true)
        messages.append(userMsg)
        isLoading = true

        Task {
            await performChatRequest(text: text)
        }
    }

    func resetConversation() {
        profile = FarmProfile()
        profileDict.removeAll()
        let resetMsg = Message(
            text: "🔄 Farm profile and conversation have been reset. Tell me your farm details to get fresh crop advice!",
            isUser: false,
            quickReplies: [
                "🌴 I have land in Goa",
                "🌾 5 acres in Punjab, irrigated",
                "🌱 Karnataka, 4 acres red soil",
                "🌧️ Maharashtra, rainfed"
            ]
        )
        messages.append(resetMsg)

        Task {
            guard let url = URL(string: "\(serverURL)/chat/reset") else { return }
            var req = URLRequest(url: url)
            req.httpMethod = "POST"
            addAPIKey(to: &req)
            _ = try? await URLSession.shared.data(for: req)
        }
    }

    private func performChatRequest(text: String) async {
        guard let url = URL(string: "\(serverURL)/chat") else {
            addBotError("Invalid server URL.")
            isLoading = false
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAPIKey(to: &request)
        request.timeoutInterval = 10.0

        let payload: [String: Any] = [
            "message": text,
            "profile": profileDict
        ]

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: payload)
            let (data, response) = try await URLSession.shared.data(for: request)

            if let httpRes = response as? HTTPURLResponse, httpRes.statusCode == 200 {
                isServerOnline = true
                if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    parseChatResponse(json)
                } else {
                    addBotError("Failed to parse response.")
                }
            } else {
                addBotError("Server returned error (Code: \((response as? HTTPURLResponse)?.statusCode ?? 500)).")
            }
        } catch {
            isServerOnline = false
            // Fallback: local rule-based response so user can test even when server is offline
            handleLocalFallback(text: text)
        }

        isLoading = false
    }

    private func addAPIKey(to request: inout URLRequest) {
        if !apiKey.isEmpty {
            request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        }
    }

    private func parseChatResponse(_ json: [String: Any]) {
        if let newProf = json["profile"] as? [String: Any] {
            self.profileDict = newProf
            updateProfileState(newProf)
        }

        let replyText = json["reply"] as? String ?? "Here are your recommendations."
        let quickReplies = json["quick_replies"] as? [String] ?? []

        var cropsList: [CropCardModel]? = nil
        var stateNote: String? = nil

        // Parse recommendation cards if present
        if let rec = json["recommendation"] as? [String: Any],
           let ranking = rec["ranking"] as? [[String: Any]] {
            cropsList = ranking.map { r in
                CropCardModel(
                    crop: r["crop"] as? String ?? "",
                    profit: (r["profit_per_acre"] as? NSNumber)?.doubleValue ?? 0.0,
                    fit: (r["fit"] as? NSNumber)?.doubleValue ?? 0.0,
                    yield: (r["yield_quintal_per_acre"] as? NSNumber)?.doubleValue ?? 0.0,
                    waterGap: (r["water_gap_mm"] as? NSNumber)?.doubleValue ?? 0.0,
                    why: r["why"] as? [String] ?? [],
                    cautions: r["cautions"] as? [String] ?? []
                )
            }

            if let st = profile.state {
                let soil = profile.soilType?.capitalized ?? "Loam"
                let irrig = (profile.irrigated ?? false) ? "Irrigated" : "Rainfed"
                let soilSrc = profile.soilSource ?? "\(st) default"
                stateNote = "📍 \(st) Baselines Applied: \(soil) soil (\(soilSrc)), \(irrig)."
            }
        }

        // Parse Plan if present
        var planModel: PlanSummaryModel? = nil
        if let planJson = json["plan"] as? [String: Any] {
            var rotList: [PlanStepModel] = []
            if let rot = planJson["rotation"] as? [String: Any],
               let steps = rot["plan"] as? [[String: Any]] {
                rotList = steps.map { s in
                    PlanStepModel(
                        season: s["season"] as? String ?? "",
                        crop: s["crop"] as? String ?? "",
                        soilHealth: (s["soil_health"] as? NSNumber)?.intValue ?? 0
                    )
                }
            }

            var taskList: [TaskItemModel] = []
            if let sched = planJson["schedule"] as? [String: Any],
               let nextTasks = sched["next_tasks"] as? [[String: Any]] {
                taskList = nextTasks.map { t in
                    TaskItemModel(
                        date: t["date"] as? String ?? "",
                        task: t["task"] as? String ?? ""
                    )
                }
            }

            let totalProfit = (planJson["allocation"] as? [String: Any])?["expected_total_profit"] as? Double ?? 0.0
            planModel = PlanSummaryModel(rotation: rotList, tasks: taskList, totalProfit: totalProfit)
        }

        let botMsg = Message(
            text: replyText,
            isUser: false,
            quickReplies: quickReplies,
            crops: cropsList,
            plan: planModel,
            stateDefaultsNote: stateNote
        )
        messages.append(botMsg)
    }

    private func updateProfileState(_ dict: [String: Any]) {
        profile.state = dict["state"] as? String
        profile.soilType = dict["soil_type"] as? String
        profile.soilSource = dict["soil_type_source"] as? String
        profile.irrigated = dict["irrigated"] as? Bool
        profile.irrigatedSource = dict["irrigated_source"] as? String
        if let ac = dict["acres"] as? NSNumber {
            profile.acres = ac.doubleValue
        }
        if let cap = dict["capital_per_acre"] as? NSNumber {
            profile.capitalPerAcre = cap.doubleValue
        }
        profile.riskTolerance = dict["risk_tolerance"] as? String
        profile.sowingDate = dict["sowing_date"] as? String
    }

    private func handleLocalFallback(text: String) {
        let t = text.lowercased()
        var matchedState: String? = nil

        // State matching
        let states = [
            "goa": "Goa", "punjab": "Punjab", "karnataka": "Karnataka",
            "maharashtra": "Maharashtra", "tamil nadu": "Tamil Nadu",
            "uttar pradesh": "Uttar Pradesh", "up": "Uttar Pradesh",
            "kerala": "Kerala", "rajasthan": "Rajasthan", "gujarat": "Gujarat",
            "haryana": "Haryana", "bihar": "Bihar", "west bengal": "West Bengal"
        ]
        for (k, v) in states {
            if t.contains(k) {
                matchedState = v
                break
            }
        }

        if let st = matchedState {
            profile.state = st
            profileDict["state"] = st
            if st == "Goa" {
                profile.soilType = "red"
                profile.irrigated = false
            } else if st == "Punjab" {
                profile.soilType = "loam"
                profile.irrigated = true
            } else if st == "Maharashtra" {
                profile.soilType = "black"
                profile.irrigated = false
            }
        }

        let offlineNotice = """
        ⚠️ Offline Mode (Backend server at \(serverURL) not reachable).

        Please run the Python server in your terminal:
        ALLOW_NO_AUTH=1 python server.py

        \(matchedState != nil ? "Detected state: \(matchedState!). Once the backend is running, you will get full profit and suitability calculations!" : "Tell me your state or start the server to get full crop advice.")
        """

        let msg = Message(
            text: offlineNotice,
            isUser: false,
            quickReplies: [
                "Retry Connection",
                "🌴 I have land in Goa",
                "🌾 5 acres in Punjab, irrigated"
            ]
        )
        messages.append(msg)
    }

    private func addBotError(_ err: String) {
        let msg = Message(
            text: "⚠️ \(err)\nMake sure server is running with 'ALLOW_NO_AUTH=1 python server.py'",
            isUser: false
        )
        messages.append(msg)
    }
}

// MARK: - Views

struct ContentView: View {
    @StateObject private var vm = ChatViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Server status & Farm HUD Banner
                StatusBanner(vm: vm)

                // Message Thread
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 14) {
                            ForEach(vm.messages) { msg in
                                MessageRowView(message: msg, onQuickReply: { reply in
                                    if reply == "Retry Connection" {
                                        Task { await vm.checkHealth() }
                                    } else {
                                        vm.sendQuickReply(reply)
                                    }
                                })
                                .id(msg.id)
                            }

                            if vm.isLoading {
                                HStack {
                                    TypingIndicatorView()
                                    Spacer()
                                }
                                .padding(.leading, 16)
                                .id("loading_indicator")
                            }
                        }
                        .padding(.vertical, 12)
                    }
                    .onChange(of: vm.messages.count) { _, _ in
                        if let lastId = vm.messages.last?.id {
                            withAnimation(.easeOut(duration: 0.25)) {
                                proxy.scrollTo(lastId, anchor: .bottom)
                            }
                        }
                    }
                }

                // Quick Prompt Carousel
                QuickPromptChipsBar(onSelect: { prompt in
                    vm.sendQuickReply(prompt)
                })

                // Input Bar
                InputBarView(inputText: $vm.inputText, isLoading: vm.isLoading, onSend: {
                    vm.sendCurrentInput()
                })
            }
            .navigationTitle("🌾 CropAdvisor")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button(action: {
                        vm.resetConversation()
                    }) {
                        Label("Reset", systemImage: "arrow.counterclockwise")
                    }
                    .help("Reset conversation and farm profile")
                }
            }
        }
    }
}

// MARK: - Subviews

struct StatusBanner: View {
    @ObservedObject var vm: ChatViewModel

    var body: some View {
        VStack(spacing: 4) {
            HStack {
                HStack(spacing: 6) {
                    Circle()
                        .fill(vm.isServerOnline ? Color.green : Color.orange)
                        .frame(width: 8, height: 8)
                    Text(vm.isServerOnline ? "API Online" : "Local / Offline")
                        .font(.caption2)
                        .fontWeight(.semibold)
                        .foregroundColor(vm.isServerOnline ? .green : .orange)
                }

                Spacer()

                if let st = vm.profile.state {
                    HStack(spacing: 4) {
                        Text("📍 \(st)")
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundColor(.primary)

                        if let soil = vm.profile.soilType {
                            Text("• \(soil.capitalized)")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }

                        if let irrig = vm.profile.irrigated {
                            Text(irrig ? "• 💧 Irrigated" : "• 🌧️ Rainfed")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }
                } else {
                    Text("No location set")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 6)
            .background(Color.chatBackground.opacity(0.8))
            Divider()
        }
    }
}

struct MessageRowView: View {
    let message: Message
    let onQuickReply: (String) -> Void

    var body: some View {
        VStack(alignment: message.isUser ? .trailing : .leading, spacing: 6) {
            HStack {
                if message.isUser { Spacer(minLength: 40) }

                VStack(alignment: message.isUser ? .trailing : .leading, spacing: 8) {
                    // State defaults tag if applicable
                    if let note = message.stateDefaultsNote {
                        Text(note)
                            .font(.caption)
                            .foregroundColor(Color(red: 0.08, green: 0.4, blue: 0.2))
                            .padding(.horizontal, 10)
                            .padding(.vertical, 4)
                            .background(Color.green.opacity(0.12))
                            .cornerRadius(6)
                    }

                    // Main text bubble
                    Text(message.text)
                        .font(.body)
                        .foregroundColor(message.isUser ? .white : .primary)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(
                            message.isUser
                                ? Color(red: 0.08, green: 0.5, blue: 0.24)
                                : Color.cardBackground
                        )
                        .cornerRadius(16)
                        .overlay(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(message.isUser ? Color.clear : Color.gray.opacity(0.2), lineWidth: 1)
                        )

                    // Crop Recommendation Cards
                    if let crops = message.crops, !crops.isEmpty {
                        VStack(spacing: 8) {
                            ForEach(Array(crops.enumerated()), id: \.element.id) { index, crop in
                                CropCardView(crop: crop, rank: index + 1)
                            }
                        }
                        .padding(.top, 4)
                    }

                    // Plan Breakdown Card
                    if let plan = message.plan {
                        PlanCardView(plan: plan)
                    }

                    // In-Message Quick Action Chips
                    if !message.quickReplies.isEmpty && !message.isUser {
                        FlowLayout(spacing: 6) {
                            ForEach(message.quickReplies, id: \.self) { reply in
                                Button(action: {
                                    onQuickReply(reply)
                                }) {
                                    Text(reply)
                                        .font(.caption)
                                        .fontWeight(.medium)
                                        .foregroundColor(Color(red: 0.08, green: 0.5, blue: 0.24))
                                        .padding(.horizontal, 10)
                                        .padding(.vertical, 5)
                                        .background(Color.green.opacity(0.1))
                                        .cornerRadius(12)
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 12)
                                                .stroke(Color.green.opacity(0.3), lineWidth: 1)
                                        )
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.top, 4)
                    }
                }

                if !message.isUser { Spacer(minLength: 40) }
            }
            .padding(.horizontal, 16)
        }
    }
}

struct CropCardView: View {
    let crop: CropCardModel
    let rank: Int

    var isTop: Bool { rank == 1 }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                HStack(spacing: 6) {
                    Text(isTop ? "🏆 Best Choice" : "#\(rank)")
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundColor(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(isTop ? Color.green : Color.blue)
                        .cornerRadius(8)

                    Text(crop.crop.capitalized)
                        .font(.headline)
                        .foregroundColor(.primary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 0) {
                    Text("₹\(Int(crop.profit).formatted())")
                        .font(.subheadline)
                        .fontWeight(.bold)
                        .foregroundColor(Color(red: 0.08, green: 0.5, blue: 0.24))
                    Text("/ acre est.")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }

            // Stats bar
            HStack(spacing: 12) {
                HStack(spacing: 4) {
                    Text("Fit:")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("\(Int(crop.fit * 100))%")
                        .font(.caption2)
                        .fontWeight(.semibold)
                }

                HStack(spacing: 4) {
                    Text("Yield:")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("\(String(format: "%.1f", crop.yield)) q/ac")
                        .font(.caption2)
                        .fontWeight(.semibold)
                }

                HStack(spacing: 4) {
                    Text("Water gap:")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text("\(Int(crop.waterGap)) mm")
                        .font(.caption2)
                        .fontWeight(.semibold)
                }
            }
            .padding(.vertical, 4)
            .padding(.horizontal, 8)
            .background(Color.primary.opacity(0.04))
            .cornerRadius(6)

            // Why points
            if !crop.why.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(crop.why, id: \.self) { reason in
                        Text("✓ \(reason)")
                            .font(.caption2)
                            .foregroundColor(Color(red: 0.08, green: 0.45, blue: 0.2))
                    }
                }
            }

            // Caution points
            if !crop.cautions.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(crop.cautions, id: \.self) { caution in
                        Text("⚠️ \(caution)")
                            .font(.caption2)
                            .foregroundColor(.orange)
                    }
                }
            }
        }
        .padding(12)
        .background(isTop ? Color.green.opacity(0.06) : Color.cardBackground)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isTop ? Color.green.opacity(0.4) : Color.gray.opacity(0.2), lineWidth: 1)
        )
    }
}

struct PlanCardView: View {
    let plan: PlanSummaryModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("📋 6-Season Rotation & Schedule")
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundColor(Color(red: 0.08, green: 0.5, blue: 0.24))

            VStack(spacing: 4) {
                ForEach(plan.rotation) { step in
                    HStack {
                        Text(step.season.capitalized)
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Spacer()
                        Text(step.crop.capitalized)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(.primary)
                        Spacer()
                        Text("Health: \(step.soilHealth)")
                            .font(.caption2)
                            .foregroundColor(Color(red: 0.08, green: 0.5, blue: 0.24))
                    }
                    Divider()
                }
            }
            .padding(8)
            .background(Color.primary.opacity(0.03))
            .cornerRadius(8)

            if !plan.tasks.isEmpty {
                Text("Upcoming Tasks:")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary)

                VStack(alignment: .leading, spacing: 4) {
                    ForEach(plan.tasks.prefix(3)) { t in
                        Text("• \(t.date): \(t.task)")
                            .font(.caption2)
                            .foregroundColor(.primary)
                    }
                }
            }
        }
        .padding(12)
        .background(Color.cardBackground)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.green.opacity(0.3), lineWidth: 1)
        )
    }
}

struct QuickPromptChipsBar: View {
    let onSelect: (String) -> Void

    let chips = [
        "🌴 I have land in Goa",
        "🌾 5 acres in Punjab, irrigated",
        "🌱 Karnataka, 4 acres red soil",
        "🌧️ Maharashtra, rainfed",
        "📋 Show full plan",
        "🌽 Can I grow maize?"
    ]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(chips, id: \.self) { chip in
                    Button(action: {
                        onSelect(chip)
                    }) {
                        Text(chip)
                            .font(.caption)
                            .foregroundColor(.primary)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(Color.cardBackground)
                            .cornerRadius(14)
                            .overlay(
                                RoundedRectangle(cornerRadius: 14)
                                    .stroke(Color.gray.opacity(0.2), lineWidth: 1)
                            )
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 6)
        }
        .background(Color.chatBackground.opacity(0.5))
    }
}

struct InputBarView: View {
    @Binding var inputText: String
    let isLoading: Bool
    let onSend: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            TextField("Type your query (e.g. 'I have land in Goa')...", text: $inputText)
                .textFieldStyle(.plain)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(Color.cardBackground)
                .cornerRadius(20)
                .overlay(
                    RoundedRectangle(cornerRadius: 20)
                        .stroke(Color.gray.opacity(0.25), lineWidth: 1)
                )
                .onSubmit {
                    if !isLoading {
                        onSend()
                    }
                }

            Button(action: onSend) {
                Image(systemName: "paperplane.fill")
                    .foregroundColor(.white)
                    .frame(width: 34, height: 34)
                    .background(Color(red: 0.08, green: 0.5, blue: 0.24))
                    .clipShape(Circle())
            }
            .buttonStyle(.plain)
            .disabled(isLoading || inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .opacity(isLoading || inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? 0.5 : 1.0)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color.chatBackground)
    }
}

struct TypingIndicatorView: View {
    var body: some View {
        HStack(spacing: 6) {
            ProgressView()
                .scaleEffect(0.7)
            Text("Calculating recommendations...")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color.cardBackground)
        .cornerRadius(12)
    }
}

// Simple FlowLayout for SwiftUI without 3rd party dependencies
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 300
        var height: CGFloat = 0
        var currentX: CGFloat = 0
        var currentY: CGFloat = 0
        var maxHeightInRow: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentX + size.width > width, currentX > 0 {
                currentX = 0
                currentY += maxHeightInRow + spacing
                maxHeightInRow = 0
            }
            currentX += size.width + spacing
            maxHeightInRow = max(maxHeightInRow, size.height)
            height = currentY + maxHeightInRow
        }
        return CGSize(width: width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var currentX = bounds.minX
        var currentY = bounds.minY
        var maxHeightInRow: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentX + size.width > bounds.maxX, currentX > bounds.minX {
                currentX = bounds.minX
                currentY += maxHeightInRow + spacing
                maxHeightInRow = 0
            }
            subview.place(at: CGPoint(x: currentX, y: currentY), proposal: ProposedViewSize(size))
            currentX += size.width + spacing
            maxHeightInRow = max(maxHeightInRow, size.height)
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
