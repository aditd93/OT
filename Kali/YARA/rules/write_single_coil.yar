rule Detect_write_single_coil
{
	meta:
		description = "Rule to detect write_single_coil packets from OT network"
		threat_level = 4
		authors = "Adi Tzurdecker, Omer Mark"

	strings:
		$modbus_write_single_coil = { ?? ?? 00 00 ?? 01 05 }
		$function_code = "Write Single Coil"
	
	condition:
		$modbus_write_single_coil or $function_code
}
