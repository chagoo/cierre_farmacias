Resources
$("#output").pivotUI(
  $.pivotUtilities.tipsData, {
    rows: ["sex", "smoker"],
    cols: ["day", "time"],
    vals: ["tip", "total_bill"],
    aggregatorName: "Sum over Sum",
    rendererName: "Heatmap"
  });