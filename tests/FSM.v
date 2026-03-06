//------------- Watch Controller -------------
`timescale 1ns / 1ns

module FSM #(
    parameter Zero    = 0 ,
    parameter Start   = 1 ,
    parameter Running = 2 ,
    parameter Stop    = 3 ,
    parameter Stopped = 4 ,
    parameter Reset   = 5
)
(
    input           Crystal      ,
    input           nSysReset    ,
    input   [1:2]   Buttons      ,
    output          WatchRunning , 
    output          WatchReset   
);

    reg [2:0] State;
    
always @(posedge Crystal or negedge nSysReset)
    if (!nSysReset)  
        State <= Zero;
    else begin
        case (State)
            Zero:
                if (Buttons[1]) State <= Start ;
            Start:
                if (!Buttons) State <= Running ;
            Running:
                if (Buttons[1]) State <= Stop  ;
            Stop:
                if (!Buttons) State <= Stopped ;
            Stopped: begin
                if (Buttons[1]) State <= Start ;
                else if (Buttons[2]) State <= Reset ;
            end
            Reset:
                if (!Buttons) State <= Zero ;
            default:
                State <= 3'bx ;
        endcase
    end

assign WatchRunning = (State == Start) || (State == Running);
assign WatchReset = (State == Reset);

endmodule