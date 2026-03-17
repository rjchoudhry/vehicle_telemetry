# Vacuum Leak Detection and Repair Validation Using ECU Telemetry

## 1. Overview
This case study documents how ECU telemetry was used to identify abnormal fuel trim behavior, form a hypothesis around unmetered air and vacuum leakage, isolate the most likely subsystem, and validate the repair using post-fix telemetry. The investigation centered on a gradually developing fault that was only subtly visible in drivability, but clearly visible in ECU behavior.

This work is an example of telemetry-driven reliability monitoring and closed-loop validation: abnormal signals were detected, a failure mechanism was inferred from operating-pattern data, the physical fault path was inspected and repaired, and the repair was verified against post-fix ECU behavior rather than subjective feel alone.

*This report documents a real-world telemetry-guided diagnosis performed on a personal vehicle platform as part of an independent vehicle reliability monitoring project.*

## 2. Vehicle / System Context
- Vehicle: 2020 Subaru WRX
- Engine: FA20DIT
- Data sources: Cobb AccessPort logs and OBD-based ECU telemetry
- Recent system change prior to fault: installation of an IAG AOS
- Monitoring focus: fuel trims, knock control behavior, and general engine health signals

The vehicle was already being monitored using repeated telemetry review, with emphasis on fueling correction, knock response, and general operating context across multiple sessions. That made it possible to detect a developing issue before it became a severe drivability problem.

## 3. Initial Symptoms
Before repair, the vehicle felt weaker and less responsive under boost. The change was noticeable but not severe enough to immediately point to a single obvious mechanical fault.

Telemetry showed a more concerning picture. Dynamic Advance Multiplier (DAM) gradually degraded from 1.0 down to 0.625, AF Learning 1 rose into the +15% to +18% range at idle, and knock-related events had been observed earlier in the investigation. The issue appeared to develop progressively rather than all at once, which suggested a fault mechanism that was worsening over time rather than a sudden hard failure.

The key point was that drivability degradation remained subtle while telemetry showed a clear and developing anomaly.

## 4. Telemetry Signals Used
The investigation relied on a small set of ECU signals that together describe fueling correction, combustion confidence, and operating context:

- Dynamic Advance Multiplier (DAM): overall ignition confidence, indicating how much timing authority the ECU is willing to maintain.
- AF Learning 1: long-term fueling correction, showing learned compensation for persistent airflow or fueling mismatch.
- AF Correction 1: short-term real-time fueling correction, showing immediate closed-loop response.
- Feedback Knock (FBK): immediate knock correction behavior in response to detected combustion instability.
- Fine Knock Learn (FKL): learned knock correction behavior retained in repeated operating cells.
- Boost / manifold vacuum: intake manifold pressure context, useful at idle as a sanity check for vacuum behavior.
- RPM: operating-state context used to compare behavior at idle versus higher engine speed.

These signals are especially useful when interpreted together rather than independently. Fuel trims can indicate airflow mismatch, while DAM and knock behavior provide context on whether that mismatch is affecting combustion confidence.

## 5. Observed Anomaly Pattern
The telemetry pattern that suggested a vacuum leak was specific and repeatable. AF Learning 1 was elevated to roughly +15% to +18% at idle, then dropped closer to about +7% by approximately 2500 RPM. Manifold vacuum at idle remained near a normal-looking value of roughly -11 psi, which meant the fault was not obvious from vacuum alone.

This pattern indicated that the ECU was adding long-term fuel to compensate for an airflow mismatch, with the strongest effect appearing in high-vacuum idle conditions. DAM had already degraded earlier in the investigation, indicating reduced combustion confidence even before the mechanical fault path had been isolated.

The idle-versus-2500 RPM trim behavior strongly suggested a small vacuum-side leak rather than a tuning issue, boost leak, or spark plug problem. A boost leak would generally present more strongly under load, while a spark-related issue would not normally produce this specific long-term fueling pattern concentrated at idle.

## 6. Hypothesis
The working hypothesis was that a small vacuum leak or unmetered air path existed in the PCV / AOS circuit, likely introduced or worsened during the AOS install.

This hypothesis was favored because the observed pattern was consistent with:
- positive long-term fuel trims,
- the strongest effect appearing at idle and high manifold vacuum,
- reduced effect at higher RPM, and
- a recent disturbance to PCV / AOS plumbing.

From an engineering standpoint, this was the highest-probability fault mechanism that explained both the fueling behavior and the installation history.

## 7. Physical Investigation
The physical inspection was focused on the intake and crankcase ventilation paths most likely to create a small unmetered-air fault.

The process included:
- inspecting the BPV, charge pipe, and intercooler area,
- checking AOS routing and quick-connect fittings,
- evaluating the PCV-side hose path,
- performing idle trim checks, hose pinch tests, and targeted spray tests, and
- removing the intercooler for improved access to the PCV-side hose and fitting.

The key finding was a torn PCV / AOS-side hose section near the clamp, located in a vacuum-critical portion of the system. That damage provided a plausible path for a small vacuum leak that would be most influential at idle.

Additional inspection showed that the PCV valve itself passed a basic directional flow and rattle test. The PCV threaded fitting had originally been installed dry and was re-sealed during the repair process.

## 8. Root Cause
The likely root cause was a small vacuum leak in the PCV-side hose and fitting path, most likely driven by hose damage near the clamp and potentially worsened by unsealed PCV threads.

The fault likely developed gradually as the damaged hose section opened further under repeated vacuum cycling. That gradual failure mode aligns with the observed telemetry trend, where trims and combustion-confidence behavior degraded over time rather than failing abruptly.

## 9. Corrective Action
The corrective action consisted of the following steps:
- removed the intercooler for access,
- repaired or replaced the damaged hose section,
- reinstalled and properly clamped the hose,
- re-sealed the PCV threaded fitting using thread sealant,
- reassembled intake and intercooler plumbing, and
- reset ECU learning to enable clean post-repair validation.

This reset was important because it allowed post-fix behavior to be evaluated without pre-existing learned compensation masking the result.

## 10. Post-Repair Validation
Post-repair telemetry showed a clear normalization of the affected signals. DAM returned to 1.000, AF Learning returned to a normal range of approximately +3% to +7%, and AF Correction remained near zero or within normal small swings. Idle vacuum remained healthy at roughly -11 psi.

Subsequent short drives showed DAM at 1, FKL = 0, and FBK = 0. In parallel with the telemetry recovery, the vehicle regained normal boost response and felt noticeably stronger and more responsive.

The combination of normalized trims, restored DAM, quiet knock metrics, and improved drivability provided strong evidence that the issue was resolved. This validation was not based on a single signal; it was based on the convergence of fueling, knock-control, and drivability evidence after corrective action.

## 11. Engineering Interpretation
From an engineering perspective, this case is useful because the fault was detectable via telemetry before it became an obvious drivability failure. Fuel trim behavior served as an early indicator of airflow mismatch, and the operating-pattern dependence of that trim behavior helped isolate the likely subsystem.

The repair was not validated by improved feel alone. Instead, pre- and post-repair ECU behavior was compared to confirm that the anomalous learned correction and reduced combustion confidence had normalized. This mirrors a real reliability and validation workflow: anomaly detection, subsystem isolation, corrective action, and post-fix validation.

## 12. Key Takeaways
- Positive AF Learning at idle can be an early indicator of small vacuum leaks.
- Comparing idle trims against higher-RPM trims is a useful way to distinguish vacuum-side leaks from other fault classes.
- PCV / AOS plumbing is a common leak source after system modifications and should be treated as a high-priority inspection area.
- Telemetry can identify faults that remain only subtly visible from the driver’s seat.
- DAM degradation can provide useful supporting evidence that airflow mismatch is affecting combustion confidence.
- Post-fix validation should include both telemetry normalization and drivability confirmation.

## 13. Future Improvements
Future improvements to this telemetry project could include automated fuel-trim anomaly flagging, case-based report generation, trend monitoring across multiple logs, and more formal validation report templates for detected faults. Those additions would make the workflow more repeatable across future fault investigations and closer to a structured validation pipeline.
