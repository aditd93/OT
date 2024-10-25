rule Detectreadcoils
{
	meta:
		description = "Rule to detect read_coils packets from OT network"
		threat_level = 4
		authors = "Adi Tzurdecker, Omer Mark"

	strings:
		$modbus_read_coils = { ?? ?? 00 00 ?? 01 01 }
		$function_code = "Read Coils"
	
	condition:
		$modbus_read_coils or $function_code
}
