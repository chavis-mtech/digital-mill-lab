import { defineMessages } from "@/lib/i18n/define";

/** Strings shared by every frontend-ops feature (model metrics, honest-baseline wording). */
export default defineMessages({
  th: {
    model: {
      title: "โมเดลและการเปรียบเทียบกับ baseline",
      name: "โมเดล",
      algorithm: "อัลกอริทึม",
      status: "สถานะ",
      trainWindow: "ช่วงข้อมูลฝึก",
      testWindow: "ช่วงข้อมูลทดสอบ (แยกตามเวลา)",
      metric: "ตัวชี้วัด",
      modelValue: "โมเดล",
      baseline: "baseline",
      verdict: "ผลเทียบ baseline",
      beats: "ดีกว่า baseline",
      loses: "ไม่ดีกว่า baseline",
      unknown: "ไม่มีผลเทียบ",
      lowerBetter: "ค่าต่ำกว่าดีกว่า",
      higherBetter: "ค่าสูงกว่าดีกว่า",
      honest: "ผลวัดบนข้อมูลสังเคราะห์ ไม่ใช่การวัดจากโรงงานจริง หากโมเดลไม่ดีกว่า baseline ระบบจะแสดงตามจริง",
      dataKind: "ชนิดข้อมูล",
    },
    simulatedNote: "เป็นการจำลอง (simulation) ไม่ใช่ข้อมูลที่เกิดขึ้นจริง",
  },
  en: {
    model: {
      title: "Model and baseline comparison",
      name: "Model",
      algorithm: "Algorithm",
      status: "Status",
      trainWindow: "Training window",
      testWindow: "Test window (temporal split)",
      metric: "Metric",
      modelValue: "Model",
      baseline: "Baseline",
      verdict: "Versus baseline",
      beats: "Beats the baseline",
      loses: "Does not beat the baseline",
      unknown: "No comparison",
      lowerBetter: "lower is better",
      higherBetter: "higher is better",
      honest: "Metrics are measured on synthetic data, not on a real plant. When a model does not beat its baseline, we show that as it is.",
      dataKind: "Data kind",
    },
    simulatedNote: "A simulation, not something that actually happened",
  },
});
