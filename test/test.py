# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, First
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray


async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100 * 100 * 0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return


def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")


async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data

    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7 - i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7 - i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)


@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000)

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")



async def rising_bit0_timeout(dut, timeout_ns):
    """
    Wait for a rising edge on bit 0 of dut.uo_out with a timeout.

    Asserts if timeout occurs.

    Returns True on success.
    """
    prev = dut.uo_out.value.integer & 1
    start_time = cocotb.utils.get_sim_time(units="ns")

    while True:
        await ClockCycles(dut.clk, 1)
        curr = dut.uo_out.value.integer & 1
        if prev == 0 and curr == 1:
            return cocotb.utils.get_sim_time(units="ns")
        prev = curr

        if cocotb.utils.get_sim_time(units="ns") - start_time > timeout_ns:
            return False

async def falling_bit0_timeout(dut, timeout_ns):
    """
    Wait for a falling edge on bit 0 of dut.uo_out with a timeout.

    Asserts if timeout occurs.

    Returns True on success.
    """
    prev = dut.uo_out.value.integer & 1
    start_time = cocotb.utils.get_sim_time(units="ns")

    while True:
        await cocotb.triggers.ClockCycles(dut.clk, 1)
        curr = dut.uo_out.value.integer & 1
        if prev == 1 and curr == 0:
            return cocotb.utils.get_sim_time(units="ns")  # falling edge detected
        prev = curr

        if cocotb.utils.get_sim_time(units="ns") - start_time > timeout_ns:
            return False

@cocotb.test()
async def test_pwm_freq(dut):
    dut._log.info("Start PWM duty cycle test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # set registers
    await send_spi_transaction(dut, 1, 0x00, 0x01) # output enable
    await send_spi_transaction(dut, 1, 0x02, 0x01) # pwm enable
    await send_spi_transaction(dut, 1, 0x04, 0x80) # set duty cycle to 50%
    await ClockCycles(dut.clk, 5)
    timeout_ns = 1e7

    # check for timeout case
    dut._log.info("Begin test for frequency")


    sample_start = await rising_bit0_timeout(dut, timeout_ns)
    assert sample_start != False, "Time out on rising edge"
    sample_end = await rising_bit0_timeout(dut, timeout_ns)
    assert sample_end != False, "Time out on falling edge"


    period = (sample_end - sample_start) * 1e-9
    frequency = 1 / period

    dut._log.info(f'Frequency: {frequency}')

    assert (2970 <= frequency <= 3030), "frequency not between 2970 and 3030"

    dut._log.info("PWM Frequency test completed successfully")

@cocotb.test()
async def test_pwm_duty(dut):
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    dut._log.info("Reset")
    dut.ena.value = 1
    dut.ui_in.value = ui_in_logicarray(1, 0, 0)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Reset Done")

    # Register setup
    await send_spi_transaction(dut, 1, 0x00, 0x01)  # output enable
    dut._log.info("transaction 1 done")
    await send_spi_transaction(dut, 1, 0x02, 0x01)  # pwm enable
    dut._log.info("transaction 2 done")
    await send_spi_transaction(dut, 1, 0x04, 0x80)  # 50% duty
    dut._log.info("transaction 3 done")

    timeout_ns = 1e7

    
    dut._log.info("Edge??")

    
    sample_1 = await rising_bit0_timeout(dut, timeout_ns)
    assert (sample_1 != False), "Timed Out on rising edge"

    sample_2 = await falling_bit0_timeout(dut, timeout_ns)
    assert (sample_2 != False), "Timed Out on falling edge"

    sample_3 = await rising_bit0_timeout(dut, timeout_ns)
    assert (sample_3 != False), "Timed Out on rising edge"



    length = sample_3 - sample_1
    time_high = sample_2 - sample_1
    duty_cycle = (time_high / length) * 100

    dut._log.info(f'Duty cycle value (should be 50%): {duty_cycle}%')
    assert 49 <= duty_cycle <= 51, "Failed 50% duty cycle test"

    # 0% duty cycle test
    await send_spi_transaction(dut, 1, 0x04, 0x00)
    timeout_ns = 1e4
    dut._log.info("Testing 0% duty cycle")

    rising_edge_0 = await rising_bit0_timeout(dut, timeout_ns)
    assert (rising_edge_0), "Signal should stay low"

    dut._log.info("Duty Cycle 0% Verified")

    # 100% duty cycle test
    await send_spi_transaction(dut, 1, 0x04, 0xFF)
    timeout_ns = 1e4
    dut._log.info("Testing 100% duty cycle")

    rising_edge_100 = await falling_bit0_timeout(dut, timeout_ns)
    assert (rising_edge_100), "Signal should stay low"

    dut._log.info("Duty Cycle 100% Verified")

    dut._log.info("PWM Duty Cycle test completed successfully")