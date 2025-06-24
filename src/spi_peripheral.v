`default_nettype none

module spi_peripheral (
    input wire clk,     // clock
    input wire rst_n,    // active-low reset
    input wire nCS,      // active-low chip select
    input wire SCLK,     // serial clock
    input wire COPI,     // controller out peripheral in

    output reg [7:0] en_reg_out_7_0,
    output reg [7:0] en_reg_out_15_8,
    output reg [7:0] en_reg_pwm_7_0,
    output reg [7:0] en_reg_pwm_15_8,
    output reg [7:0] pwm_duty_cycle
);

    // CDC synchronization registers
    reg [1:0] nCS_sync;
    reg [1:0] SCLK_sync;
    reg [1:0] COPI_sync;

    // SPI transaction registers
    reg [4:0] SCLK_count;
    reg [15:0] data_in;

    always @(posedge clk or negedge rst_n) begin
    // clk_counter is only updated every positive clock edge
    // or when reset is tripped
        if (!rst_n) begin
            en_reg_out_7_0 <= '0;
            en_reg_out_15_8 <= '0;
            en_reg_pwm_7_0 <= '0;
            en_reg_pwm_15_8 <= '0;
            pwm_duty_cycle <= '0;

            nCS_sync <= '0;
            SCLK_sync <= '0;
            COPI_sync <= '0;
            SCLK_count <= '0;
            data_in <= '0;
        end else begin
            
            nCS_sync <= {nCS_sync[0], nCS};  // Buffers used for syncing with clocks
            SCLK_sync <= {SCLK_sync[0], SCLK};
            COPI_sync <= {COPI_sync[0], COPI};

            if (nCS_sync == 2'b10) begin // Chip is turned on, reset stuff
                SCLK_count <= '0;
                data_in <= '0;
            end 
            
            else if (SCLK_sync == 2'b01) begin
                if (SCLK_count <= 5'd15) begin
                    SCLK_count <= SCLK_count + 1;
                    data_in <= {data_in[14:0], COPI_sync[1]}; // Read previous measure point to deal with CDC
                end
            end

            if (nCS_sync == 2'b01 && SCLK_count == 5'd16) begin // Check SPI has finished and that 16 bits were recieved
                if (data_in[15]) begin
                    case(data_in[14:8])
                        7'h00       : en_reg_out_7_0 <= data_in[7:0];
                        7'h01       : en_reg_out_15_8 <= data_in[7:0];
                        7'h02       : en_reg_pwm_7_0 <= data_in[7:0];
                        7'h03       : en_reg_pwm_15_8 <= data_in[7:0];
                        7'h04       : pwm_duty_cycle <= data_in[7:0];
                        default     : ; // Invalid address
                    endcase
                end
            end
        end
    end

endmodule
