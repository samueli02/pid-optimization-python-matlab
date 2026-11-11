function result = verify_pid(configPath, pythonCsvPath, outputDir)
%VERIFY_PID Independent MATLAB replay of Python's explicit sampled PID.
% Uses tf/ss/c2d if Control System Toolbox is installed and usable; otherwise
% base MATLAB constructs a controllable canonical realization and exact ZOH
% with an augmented matrix exponential. No toolbox or Simulink is required.
% Example: verify_pid('results/benchmark/optimized/config.json', ...
%   'results/benchmark/optimized/python_results.csv', 'results/benchmark/matlab');
% CSV contract: t,y,u (additional columns are ignored).
arguments
    configPath (1,:) char
    pythonCsvPath (1,:) char = ''
    outputDir (1,:) char = 'results/matlab'
end
c = jsondecode(fileread(configPath));
dt = c.sim.dt;
N = floor(c.sim.horizon/dt + 0.5);
t = (0:N)'*dt;
delay = floor(c.plant.delay/dt + 0.5);
[Ad,Bd,Cd,Dd,plantMethod] = discretize_plant(c.plant.num,c.plant.den,dt);
assert(max(abs(Dd),[],'all') < 1e-12,'Strictly proper plant required');
Kp = c.pid.kp; Ki = c.pid.ki; Kd = c.pid.kd; Tf = c.pid.tf;
r = c.sim.setpoint;
x = zeros(size(Ad,1),1);
queue = zeros(max(1,delay),1); cursor = 1;
I = 0; derivative = 0; previousError = r;
alpha = Tf/(Tf+dt);
y = zeros(N+1,1); u = y; e = y;
for k=1:N+1
    y(k) = Cd*x;
    e(k) = r-y(k);
    if k > 1
        % Lecture 3: composite trapezoid accumulation of error.
        I = I + dt*(e(k)+previousError)/2;
        % Backward finite difference followed by a low-pass derivative filter.
        derivative = alpha*derivative+(e(k)-previousError)/(Tf+dt);
    end
    u(k) = Kp*e(k)+Ki*I+Kd*derivative;
    previousError = e(k);
    assert(isfinite(u(k)) && max(abs([x;y(k);u(k)])) < 1e10,'Simulation diverged');
    if k <= N
        if delay > 0
            applied = queue(cursor); queue(cursor)=u(k);
            cursor = mod(cursor,delay)+1;
        else
            applied = u(k);
        end
        x = Ad*x+Bd*applied;
    end
end
Acl = augmented_matrix(Ad,Bd,Cd,Kp,Ki,Kd,Tf,dt,delay);
rho = max(abs(eig(Acl)));
stable = rho < 1-1e-9;
itae = dt*(sum(t.*abs(e))-(t(1)*abs(e(1))+t(end)*abs(e(end)))/2);
ise = dt*(sum(e.^2)-(e(1)^2+e(end)^2)/2);
outside = find(abs(e)>0.02*abs(r));
settling = NaN;
if stable && isempty(outside)
    settling=0;
elseif stable && outside(end)<length(t)
    settling=t(outside(end)+1);
end
metrics=struct('itae',itae,'ise',ise,'overshoot_pct',max(0,100*(max(y/r)-1)), ...
    'settling_time',settling,'steady_error',abs(e(end)), ...
    'spectral_radius',rho,'stable',stable,'effective_delay',delay*dt, ...
    'effective_horizon',t(end),'delay_samples',delay,'peak_control',max(abs(u)));
if strcmpi(c.objective,'ITAE'), metrics.cost=itae; else, metrics.cost=ise; end
if ~stable, metrics.cost=1e12+min(rho,1e6)*1e6; end
if ~isfolder(outputDir), mkdir(outputDir); end
writetable(table(t,y,u,e),fullfile(outputDir,'matlab_results.csv'));
comparison=struct('python_csv_supplied',~isempty(pythonCsvPath));
py=[];
if ~isempty(pythonCsvPath)
    py=readtable(pythonCsvPath,'VariableNamingRule','preserve');
    assert(all(ismember({'t','y','u'},py.Properties.VariableNames)), ...
        'Python CSV must include t,y,u columns');
    assert(height(py)==length(t),'Python/MATLAB sample counts differ');
    comparison.max_abs_t=max(abs(py.t-t));
    comparison.max_abs_y=max(abs(py.y-y));
    comparison.max_abs_u=max(abs(py.u-u));
    pyE=r-py.y;
    pyItae=dt*(sum(t.*abs(pyE))-(t(1)*abs(pyE(1))+t(end)*abs(pyE(end)))/2);
    pyIse=dt*(sum(pyE.^2)-(pyE(1)^2+pyE(end)^2)/2);
    comparison.abs_itae_difference=abs(pyItae-itae);
    comparison.abs_ise_difference=abs(pyIse-ise);
    comparison.tolerance=1e-7;
    comparison.passed=comparison.max_abs_t<1e-10 && ...
        comparison.max_abs_y<comparison.tolerance && comparison.max_abs_u<comparison.tolerance;
end
save_comparison_figure(t,y,u,e,r,py,outputDir);
result=struct('metrics',metrics,'comparison',comparison, ...
    'method',[plantMethod,'; explicit trapezoid/filtered-difference PID'], ...
    'matlab_version',version, ...
    'visualizations',{{'matlab_python_comparison.png','matlab_python_comparison.fig'}});
fid=fopen(fullfile(outputDir,'matlab_comparison.json'),'w');
assert(fid~=-1,'Cannot write comparison JSON');
cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s',jsonencode(result,PrettyPrint=true));
disp(result);
end

function save_comparison_figure(t,y,u,e,r,py,outputDir)
% Generate directly from MATLAB's independent replay, without a visible GUI.
fig=figure('Visible','off','Color','white','Position',[100,100,1200,760]);
cleanup=onCleanup(@()close(fig)); %#ok<NASGU>
layout=tiledlayout(fig,2,2,'TileSpacing','compact','Padding','compact');
title(layout,'Independent MATLAB replay versus Python');
nexttile(layout,1);
plot(t,y,'LineWidth',1.7,'DisplayName','MATLAB'); hold on;
yline(r,':','LineWidth',1.1,'DisplayName','Setpoint');
if ~isempty(py), plot(py.t,py.y,'--','LineWidth',1.2,'DisplayName','Python'); end
xlabel('Time (s)'); ylabel('Output y'); title('Step response'); grid on; legend('Location','best');
nexttile(layout,2);
plot(t,u,'LineWidth',1.7,'DisplayName','MATLAB'); hold on;
if ~isempty(py), plot(py.t,py.u,'--','LineWidth',1.2,'DisplayName','Python'); end
xlabel('Time (s)'); ylabel('Control input u'); title('Control action'); grid on; legend('Location','best');
nexttile(layout,3);
if ~isempty(py)
    plot(t,y-py.y,'LineWidth',1.2);
    ylabel('y_{MATLAB} - y_{Python}'); title('Output difference');
else
    plot(t,e,'LineWidth',1.2); ylabel('Tracking error'); title('Tracking error');
end
xlabel('Time (s)'); grid on;
nexttile(layout,4);
if ~isempty(py)
    plot(t,u-py.u,'LineWidth',1.2);
    ylabel('u_{MATLAB} - u_{Python}'); title('Control-input difference');
else
    plot(t,t.*abs(e),'LineWidth',1.2); ylabel('t |e(t)|'); title('ITAE integrand');
end
xlabel('Time (s)'); grid on;
exportgraphics(fig,fullfile(outputDir,'matlab_python_comparison.png'),'Resolution',180);
savefig(fig,fullfile(outputDir,'matlab_python_comparison.fig'));
end

function [Ad,Bd,Cd,Dd,method]=discretize_plant(num,den,h)
% Independent MATLAB implementation; it does not read Python state matrices.
if exist('tf','file')~=0 && exist('c2d','file')~=0 && exist('ss','file')~=0
    try
        plant=ss(tf(num(:)',den(:)'));
        [Ad,Bd,Cd,Dd]=ssdata(c2d(plant,h,'zoh'));
        method='Control System Toolbox tf/ss/c2d ZOH';
        return
    catch toolboxError
        warning('PIDLab:ToolboxFallback','Toolbox path unavailable: %s. Using base MATLAB.',toolboxError.message);
    end
end
num=num(:)'; den=den(:)';
first=find(den~=0,1); assert(~isempty(first),'Zero denominator'); den=den(first:end);
first=find(num~=0,1); assert(~isempty(first),'Zero numerator'); num=num(first:end);
num=num/den(1); den=den/den(1);
n=length(den)-1;
assert(n>=1 && length(num)<length(den),'A strictly proper plant is required');
num=[zeros(1,n+1-length(num)),num];
% Controllable canonical form for descending-power polynomial coefficients.
A=zeros(n); A(1,:)=-den(2:end);
if n>1, A(2:end,1:end-1)=eye(n-1); end
B=[1;zeros(n-1,1)];
Dd=num(1); Cd=num(2:end)-Dd*den(2:end);
% expm([A B;0 0]*h) = [Ad Bd;0 1], including singular A without inv(A).
transition=expm([A,B;zeros(1,n+1)]*h);
Ad=transition(1:n,1:n); Bd=transition(1:n,n+1);
method='Base MATLAB controllable canonical form + augmented expm ZOH';
end

function Acl=augmented_matrix(Ad,Bd,Cd,Kp,Ki,Kd,Tf,h,delay)
% Controller states with zero gains are omitted, matching the Python test.
n=size(Ad,1); count=n; iI=0; iD=0; iE=0;
if Ki~=0, count=count+1; iI=count; end
if Kd~=0, count=count+1; iD=count; end
if Ki~=0 || Kd~=0, count=count+1; iE=count; end
queueStart=count+1; count=count+delay;
Acl=zeros(count); er=zeros(1,count); er(1:n)=-Cd;
control=Kp*er;
if Ki~=0
    row=h/2*er; row(iI)=row(iI)+1; row(iE)=row(iE)+h/2;
    Acl(iI,:)=row; control=control+Ki*row;
end
if Kd~=0
    row=er/(Tf+h); row(iD)=row(iD)+Tf/(Tf+h); row(iE)=row(iE)-1/(Tf+h);
    Acl(iD,:)=row; control=control+Kd*row;
end
if iE~=0, Acl(iE,:)=er; end
Acl(1:n,1:n)=Ad;
if delay>0
    Acl(1:n,queueStart)=Acl(1:n,queueStart)+Bd;
    for j=0:delay-2, Acl(queueStart+j,queueStart+j+1)=1; end
    Acl(end,:)=control;
else
    Acl(1:n,:)=Acl(1:n,:)+Bd*control;
end
end
